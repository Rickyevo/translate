#include <windows.h>
#include <psapi.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
typedef LONG (NTAPI *WriteFn)(HANDLE,HANDLE,PVOID,PVOID,PVOID,PVOID,ULONG,PVOID,PVOID);
typedef struct { union { LONG status; PVOID ptr; }; ULONG_PTR information; } IOS;
static volatile LONG64 delivered;
static DWORD WINAPI drain(LPVOID h) {
    BYTE buf[65536]; DWORD n;
    while(ReadFile(h,buf,sizeof(buf),&n,NULL))InterlockedAdd64(&delivered,n);
    return 0;
}
static int cmp(const void*a,const void*b){double x=*(double*)a,y=*(double*)b; return (x>y)-(x<y);}
static void memory(void) {
    PROCESS_MEMORY_COUNTERS_EX p={sizeof(p)};
    GetProcessMemoryInfo(GetCurrentProcess(),(PROCESS_MEMORY_COUNTERS*)&p,sizeof(p));
    printf("\"private_mb\":%.6f,\"ws_mb\":%.6f",p.PrivateUsage/1048576.,p.WorkingSetSize/1048576.);
}
int main(void) {
    HMODULE dll=NULL;
    printf("{\"pid\":%lu}\n",GetCurrentProcessId()); fflush(stdout);
    static char line[600000],verb[32],arg[524300];
    while(fgets(line,sizeof(line),stdin)) {
        int count=0; arg[0]=0;
        if(sscanf_s(line,"%31s %d %524299s",verb,32,&count,arg,(unsigned)sizeof(arg))<1)break;
        if(!strcmp(verb,"quit"))break;
        if(!strcmp(verb,"load")) {
            dll=LoadLibraryA(arg);
            DWORD result=dll?((DWORD(*)(void))GetProcAddress(dll,"Start"))():999;
            printf("{\"load\":%lu,",result); memory(); puts("}"); fflush(stdout); continue;
        }
        if(!strcmp(verb,"stop")) {
            DWORD result=((DWORD(*)(void))GetProcAddress(dll,"Stop"))();
            printf("{\"stop\":%lu}\n",result); fflush(stdout); continue;
        }
        if(!strcmp(verb,"mem")) { printf("{");memory();puts("}");fflush(stdout);continue; }
        if(count<1 || count>20000)return 10;
        DWORD len=(DWORD)strlen(arg)/2;
        BYTE *data=malloc(len);
        for(DWORD i=0;i<len;i++){unsigned x;sscanf_s(arg+i*2,"%2x",&x);data[i]=(BYTE)x;}
        wchar_t name[160];
        swprintf_s(name,160,L"\\\\.\\pipe\\%s_%lu_%llu",!strcmp(verb,"other")?L"unrelated_feasibility":L"session_v2_feasibility",GetCurrentProcessId(),GetTickCount64());
        HANDLE server=CreateNamedPipeW(name,PIPE_ACCESS_INBOUND,PIPE_TYPE_BYTE|PIPE_WAIT,1,65536,65536,0,NULL);
        BOOL async=!strcmp(verb,"async");
        HANDLE client=CreateFileW(name,GENERIC_WRITE,0,NULL,OPEN_EXISTING,async?FILE_FLAG_OVERLAPPED:0,NULL);
        if(server==INVALID_HANDLE_VALUE||client==INVALID_HANDLE_VALUE)return 11;
        ConnectNamedPipe(server,NULL);
        HANDLE reader=CreateThread(NULL,0,drain,server,0,NULL);
        WriteFn nt=(WriteFn)GetProcAddress(GetModuleHandleW(L"ntdll.dll"),"NtWriteFile");
        LARGE_INTEGER freq,a,b; QueryPerformanceFrequency(&freq);
        double *times=malloc(count*sizeof(double));
        LONG64 initial=delivered;
        int errors=0;
        HANDLE event=CreateEventW(NULL,TRUE,FALSE,NULL);
        for(int i=0;i<count;i++) {
            DWORD n=0; QueryPerformanceCounter(&a);
            if(!strcmp(verb,"nt")) { IOS ios={0}; if(nt(client,NULL,NULL,NULL,&ios,data,len,NULL,NULL)!=0)errors++; }
            else { OVERLAPPED ov={0};ov.hEvent=event;ResetEvent(event);
                BOOL ok=WriteFile(client,data,len,&n,async?&ov:NULL);
                if(!ok && async && GetLastError()==ERROR_IO_PENDING)ok=GetOverlappedResult(client,&ov,&n,TRUE);
                if(!ok || n!=len)errors++;
            }
            QueryPerformanceCounter(&b);times[i]=(b.QuadPart-a.QuadPart)*1000000./freq.QuadPart;
            /* Intentional rate limit, outside measured call time, lets consumer drain bounded ring. */
            Sleep(1);
        }
        CloseHandle(client);WaitForSingleObject(reader,5000);
        qsort(times,count,sizeof(double),cmp);
        printf("{\"mode\":\"%s\",\"count\":%d,\"len\":%lu,\"delivered\":%lld,\"errors\":%d,\"median_us\":%.4f,\"p95_us\":%.4f,",verb,count,len,delivered-initial,errors,times[count/2],times[(count-1)*95/100]);
        memory(); puts("}");fflush(stdout);
        CloseHandle(event);CloseHandle(reader);CloseHandle(server);free(times);free(data);
    }
    return 0;
}
