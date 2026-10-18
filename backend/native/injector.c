/* Narrow x64 loader. Invoked as a short-lived child; no runtime stays in Python.
 * Only named WeType / owned-fixture targets are accepted. No remote shell/code. */
#include "transport.h"
#include <tlhelp32.h>
#include <stdio.h>
#include <wchar.h>
static uintptr_t module_base(DWORD pid,const wchar_t*name){
    HANDLE snap=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE|TH32CS_SNAPMODULE32,pid);if(snap==INVALID_HANDLE_VALUE)return 0;
    MODULEENTRY32W e={sizeof(e)};uintptr_t result=0;
    if(Module32FirstW(snap,&e))do{if(!_wcsicmp(e.szModule,name)){result=(uintptr_t)e.modBaseAddr;break;}}while(Module32NextW(snap,&e));
    CloseHandle(snap);return result;
}
static DWORD remote_call(HANDLE process,PVOID address,PVOID argument){
    HANDLE thread=CreateRemoteThread(process,NULL,0,(LPTHREAD_START_ROUTINE)address,argument,0,NULL);
    if(!thread)return 0xffff0000|GetLastError();
    DWORD result=0;
    if(WaitForSingleObject(thread,10000)!=WAIT_OBJECT_0)result=0xfffe0000;
    else GetExitCodeThread(thread,&result);
    CloseHandle(thread);return result;
}
int wmain(int argc,wchar_t**argv){
    if(argc!=8)return 2;
    DWORD pid=wcstoul(argv[1],NULL,10),controller=wcstoul(argv[3],NULL,10),error=0;
    HANDLE process=OpenProcess(PROCESS_CREATE_THREAD|PROCESS_VM_OPERATION|PROCESS_VM_READ|PROCESS_VM_WRITE|PROCESS_QUERY_INFORMATION|SYNCHRONIZE,FALSE,pid);
    if(!process){printf("{\"error\":%lu,\"stage\":\"open\"}\n",GetLastError());return 3;}
    FILETIME created,exited,kernel,user;
    if(!GetProcessTimes(process,&created,&exited,&kernel,&user)||(((UINT64)created.dwHighDateTime<<32)|created.dwLowDateTime)!=_wcstoui64(argv[7],NULL,10)){error=214;goto finish;}
    wchar_t image[32768];DWORD size=32768;
    if(!QueryFullProcessImageNameW(process,0,image,&size)){error=201;goto finish;}
    wchar_t*name=wcsrchr(image,L'\\');name=name?name+1:image;
    if(_wcsicmp(name,L"wetype_server.exe")&&_wcsicmp(name,L"feasibility_fixture.exe")){error=202;goto finish;}
    USHORT machine=0,native=0;
    if(!IsWow64Process2(process,&machine,&native)||machine!=IMAGE_FILE_MACHINE_UNKNOWN||native!=IMAGE_FILE_MACHINE_AMD64){error=203;goto finish;}
    wchar_t full[MAX_PATH];if(!GetFullPathNameW(argv[2],MAX_PATH,full,NULL)){error=204;goto finish;}
    HMODULE local=LoadLibraryExW(full,NULL,DONT_RESOLVE_DLL_REFERENCES);if(!local){error=205;goto finish;}
    PVOID exported=GetProcAddress(local,"TranslateObserverStart");
    if(!exported){FreeLibrary(local);error=206;goto finish;}
    uintptr_t rva=(uintptr_t)exported-(uintptr_t)local;FreeLibrary(local);
    const wchar_t*dll_name=wcsrchr(full,L'\\');dll_name=dll_name?dll_name+1:full;
    uintptr_t remote=module_base(pid,dll_name);
    if(!remote){
        PVOID loader=GetProcAddress(GetModuleHandleW(L"kernel32.dll"),"LoadLibraryW");HMODULE owner=NULL;
        if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,(LPCWSTR)loader,&owner)){error=207;goto finish;}
        wchar_t owner_path[MAX_PATH];GetModuleFileNameW(owner,owner_path,MAX_PATH);wchar_t*owner_name=wcsrchr(owner_path,L'\\');owner_name=owner_name?owner_name+1:owner_path;
        uintptr_t owner_remote=module_base(pid,owner_name);if(!owner_remote){error=208;goto finish;}
        SIZE_T bytes=(wcslen(full)+1)*sizeof(wchar_t);PVOID buffer=VirtualAllocEx(process,NULL,bytes,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
        if(!buffer){error=209;goto finish;}
        if(!WriteProcessMemory(process,buffer,full,bytes,NULL)){VirtualFreeEx(process,buffer,0,MEM_RELEASE);error=210;goto finish;}
        DWORD loaded=remote_call(process,(PVOID)(owner_remote+(uintptr_t)loader-(uintptr_t)owner),buffer);
        // On a timeout the target may still use its argument; leave that small
        // allocation until process exit instead of freeing it under the loader.
        if(loaded!=0xfffe0000)VirtualFreeEx(process,buffer,0,MEM_RELEASE);
        remote=module_base(pid,dll_name);if(!remote){error=211;goto finish;}
    }
    TrConfig config={TR_VERSION,controller};
    wcsncpy_s(config.mapping,160,argv[4],_TRUNCATE);wcsncpy_s(config.data_event,160,argv[5],_TRUNCATE);wcsncpy_s(config.control_event,160,argv[6],_TRUNCATE);
    PVOID argument=VirtualAllocEx(process,NULL,sizeof(config),MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
    if(!argument){error=212;goto finish;}
    if(!WriteProcessMemory(process,argument,&config,sizeof(config),NULL)){VirtualFreeEx(process,argument,0,MEM_RELEASE);error=213;goto finish;}
    error=remote_call(process,(PVOID)(remote+rva),argument);
    if(error!=0xfffe0000)VirtualFreeEx(process,argument,0,MEM_RELEASE);
finish:
    CloseHandle(process);printf("{\"error\":%lu}\n",error);return error?1:0;
}
