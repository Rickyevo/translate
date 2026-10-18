#pragma once
#include <windows.h>
#include <stdint.h>
#define TR_MAGIC 0x54524e32u
#define TR_VERSION 1
#define TR_SLOTS 64
#define TR_CHUNK 32768
#define TR_MAX_WRITE 262144
#define TR_RUNNING 1
#define TR_STOPPING 2
#define TR_STOPPED 3
/* Fixed x64 ABI. Keep Python's struct definitions in native_transport.py in sync. */
typedef struct {
    volatile LONG64 ready;
    UINT64 generation,handle,tick;
    DWORD length,reserved;
    BYTE data[TR_CHUNK];
} TrSlot;
typedef struct {
    DWORD magic,version,slots,chunk;
    volatile LONG64 write,read,loss,heartbeat;
    volatile LONG state,stop;
    DWORD controller_pid,allowed_foreground_pid;
    TrSlot slot[TR_SLOTS];
} TrRing;
typedef struct {
    DWORD version,controller_pid;
    wchar_t mapping[160],data_event[160],control_event[160];
} TrConfig;
typedef LONG(NTAPI *TrWrite)(HANDLE,HANDLE,PVOID,PVOID,PVOID,PVOID,ULONG,PVOID,PVOID);
