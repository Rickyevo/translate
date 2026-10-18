/* Read-only NtWriteFile observer. No parser, Python, JS, network, or input injection.
 * Original writes never wait for the observer queue. Any gap invalidates the stream.
 * Hook/trampoline code stays resident for target lifetime; leases/views do not. */
#include "transport.h"
#include "MinHook.h"
#include <wchar.h>
static TrWrite original;
static PVOID target;
static TrRing *volatile ring;
static volatile LONG active,lease;
static volatile LONG flight[256];
static HANDLE data_event,control_event,mapping;
static __declspec(thread) int reentrant;

static BOOL is_target_pipe(HANDLE h){
    if(GetFileType(h)!=FILE_TYPE_PIPE)return FALSE;
    BYTE info[2048];
    if(!GetFileInformationByHandleEx(h,FileNameInfo,info,sizeof(info)))return FALSE;
    FILE_NAME_INFO *n=(FILE_NAME_INFO*)info;
    DWORD count=n->FileNameLength/2;if(count>1020)count=1020;n->FileName[count]=0;
    return wcsstr(n->FileName,L"session_v2")||wcsstr(n->FileName,L"server_for_renderer");
}
static LONG64 reserve(TrRing*r,LONG count){
    for(int attempts=0;attempts<16;attempts++){
        LONG64 w=InterlockedCompareExchange64(&r->write,0,0);
        LONG64 rd=InterlockedCompareExchange64(&r->read,0,0);
        if(w<rd||w-rd+count>TR_SLOTS)return -1;
        if(InterlockedCompareExchange64(&r->write,w+count,w)==w)return w;
    }return -1;
}
static LONG NTAPI observed(HANDLE h,HANDLE event,PVOID apc,PVOID context,PVOID ios,PVOID buffer,ULONG length,PVOID offset,PVOID key){
    InterlockedIncrement(&active);
    TrRing*r=(TrRing*)InterlockedCompareExchangePointer((PVOID volatile*)&ring,NULL,NULL);
    LONG64 ticket=-1;LONG parts=0;BOOL held=FALSE,copied=FALSE;UINT64 generation=0;
    ULONG bucket=((ULONG_PTR)h>>2)&255;
    if(!reentrant&&r&&r->state==TR_RUNNING&&length){
        reentrant=1;
        DWORD pid=0;
        if(r->allowed_foreground_pid)GetWindowThreadProcessId(GetForegroundWindow(),&pid);
        if((!r->allowed_foreground_pid||pid==r->allowed_foreground_pid)&&is_target_pipe(h)){
            // Ambiguous concurrent writes on a handle/shard are discontinuities,
            // never interleaved into a plausible but incorrect candidate frame.
            held=InterlockedCompareExchange(&flight[bucket],1,0)==0;
            if(!held||length>TR_MAX_WRITE)InterlockedIncrement64(&r->loss);
            else{
                parts=(length+TR_CHUNK-1)/TR_CHUNK;
                generation=InterlockedCompareExchange64(&r->loss,0,0);
                ticket=reserve(r,parts);
                if(ticket<0)InterlockedIncrement64(&r->loss);
                else{
                    __try{
                        for(LONG i=0;i<parts;i++){
                            TrSlot*s=&r->slot[(ticket+i)%TR_SLOTS];
                            DWORD n=length-i*TR_CHUNK;if(n>TR_CHUNK)n=TR_CHUNK;
                            s->generation=generation;s->handle=(UINT64)h;s->tick=GetTickCount64();s->length=n;s->reserved=0;
                            memcpy(s->data,(BYTE*)buffer+i*TR_CHUNK,n);
                        }copied=TRUE;
                    }__except(EXCEPTION_EXECUTE_HANDLER){InterlockedIncrement64(&r->loss);}
                }
            }
        }
        reentrant=0;
    }
    LONG result=original(h,event,apc,context,ios,buffer,length,offset,key);
    if(ticket>=0){
        if(!copied||(result!=0&&result!=0x103))for(LONG i=0;i<parts;i++)r->slot[(ticket+i)%TR_SLOTS].length=0;
        // Publish the first chunk last; the consumer cannot see half a group.
        for(LONG i=parts-1;i>=0;i--)InterlockedExchange64(&r->slot[(ticket+i)%TR_SLOTS].ready,ticket+i+1);
        SetEvent(data_event);
    }
    if(held)InterlockedExchange(&flight[bucket],0);
    InterlockedDecrement(&active);
    return result;
}
static DWORD WINAPI watch(LPVOID unused){
    TrRing*r=ring;
    while(!r->stop&&GetTickCount64()-(UINT64)InterlockedCompareExchange64(&r->heartbeat,0,0)<5000){
        WaitForSingleObject(control_event,250);
    }
    InterlockedExchange(&r->state,TR_STOPPING);
    MH_DisableHook(target);
    // Detours that have not loaded a lease yet see NULL; existing readers are
    // counted before they load it. The resident trampoline remains valid.
    InterlockedExchangePointer((PVOID volatile*)&ring,NULL);
    while(InterlockedCompareExchange(&active,0,0))Sleep(1);
    InterlockedExchange(&r->state,TR_STOPPED);SetEvent(data_event);
    UnmapViewOfFile(r);CloseHandle(mapping);CloseHandle(data_event);CloseHandle(control_event);
    mapping=data_event=control_event=NULL;
    InterlockedExchange(&lease,0);return 0;
}
__declspec(dllexport) DWORD WINAPI TranslateObserverStart(LPVOID parameter){
    TrConfig config;
    __try{memcpy(&config,parameter,sizeof(config));}__except(EXCEPTION_EXECUTE_HANDLER){return 100;}
    if(config.version!=TR_VERSION)return 101;
    config.mapping[159]=config.data_event[159]=config.control_event[159]=0;
    wchar_t exe[MAX_PATH];GetModuleFileNameW(NULL,exe,MAX_PATH);wchar_t*name=wcsrchr(exe,L'\\');name=name?name+1:exe;
    if(_wcsicmp(name,L"wetype_server.exe")&&_wcsicmp(name,L"feasibility_fixture.exe"))return 102;
    if(InterlockedCompareExchange(&lease,1,0))return ERROR_BUSY;
    DWORD error=103;
    mapping=OpenFileMappingW(FILE_MAP_READ|FILE_MAP_WRITE,FALSE,config.mapping);
    if(!mapping)goto fail;
    ring=MapViewOfFile(mapping,FILE_MAP_READ|FILE_MAP_WRITE,0,0,sizeof(TrRing));
    if(!ring)goto fail;
    if(ring->magic!=TR_MAGIC||ring->version!=TR_VERSION||ring->slots!=TR_SLOTS||ring->chunk!=TR_CHUNK||ring->controller_pid!=config.controller_pid){error=104;goto fail;}
    data_event=OpenEventW(EVENT_MODIFY_STATE,FALSE,config.data_event);
    control_event=OpenEventW(SYNCHRONIZE,FALSE,config.control_event);
    if(!data_event||!control_event){error=105;goto fail;}
    if(!original){
        if(MH_Initialize()!=MH_OK){error=106;goto fail;}
        target=GetProcAddress(GetModuleHandleW(L"ntdll.dll"),"NtWriteFile");
        if(MH_CreateHook(target,observed,(LPVOID*)&original)!=MH_OK){error=107;goto fail;}
    }
    InterlockedExchange(&ring->state,TR_RUNNING);
    if(MH_EnableHook(target)!=MH_OK){error=108;goto fail;}
    HANDLE worker=CreateThread(NULL,0,watch,NULL,0,NULL);
    if(!worker){MH_DisableHook(target);error=109;goto fail;}
    CloseHandle(worker);return 0;
fail:
    if(ring){
        if(original&&target)MH_DisableHook(target);
        TrRing*old=(TrRing*)InterlockedExchangePointer((PVOID volatile*)&ring,NULL);
        while(InterlockedCompareExchange(&active,0,0))Sleep(1);
        UnmapViewOfFile(old);
    }
    if(mapping)CloseHandle(mapping);if(data_event)CloseHandle(data_event);if(control_event)CloseHandle(control_event);
    mapping=data_event=control_event=NULL;InterlockedExchange(&lease,0);return error;
}
BOOL WINAPI DllMain(HINSTANCE module,DWORD reason,LPVOID reserved){return TRUE;}
__declspec(dllexport) LONG64 WINAPI TranslateAtomicLoad64(volatile LONG64*value){return InterlockedCompareExchange64(value,0,0);}
__declspec(dllexport) void WINAPI TranslateAtomicStore64(volatile LONG64*value,LONG64 next){InterlockedExchange64(value,next);}
