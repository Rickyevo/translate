"""Bounded native IPC, x64 Windows only. No Frida import or frontend protocol change.

The target owns a 2 MiB ring; at most eight 32 KiB packets await dispatch in Python.
Queue gaps are explicit: invalidate the source and require a fresh composition.
The injected lease disables itself on controller stop/crash/heartbeat expiry.
"""
from __future__ import annotations
import ctypes as C
from ctypes import wintypes as W
import json
import hashlib
from functools import wraps
import mmap
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import threading
import time
import uuid
from .. import win32

MAGIC, VERSION, SLOTS, CHUNK = 0x54524e32, 1, 64, 32768
HEADER = struct.Struct('<IIIIqqqqiiII')
SLOT = struct.Struct('<QQQQII')
STRIDE = SLOT.size + CHUNK
SIZE = HEADER.size + SLOTS * STRIDE
RUNNING, STOPPING, STOPPED = 1, 2, 3
k = C.WinDLL('kernel32', use_last_error=True)
k.GetCurrentProcess.restype = W.HANDLE
k.GetTickCount64.restype = C.c_uint64
k.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
k.WaitForMultipleObjects.argtypes = [W.DWORD, C.POINTER(W.HANDLE), W.BOOL, W.DWORD]
k.SetEvent.argtypes = [W.HANDLE]
k.CloseHandle.argtypes = [W.HANDLE]
k.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
k.OpenProcess.restype = W.HANDLE
k.GetProcessTimes.argtypes = [W.HANDLE] + [C.POINTER(W.FILETIME)] * 4
k.ProcessIdToSessionId.argtypes = [W.DWORD, C.POINTER(W.DWORD)]
k.CreateToolhelp32Snapshot.argtypes = [W.DWORD,W.DWORD]
k.CreateToolhelp32Snapshot.restype = W.HANDLE
k.Process32FirstW.argtypes = [W.HANDLE,C.POINTER(win32._PROCESSENTRY32W)]
k.Process32NextW.argtypes = [W.HANDLE,C.POINTER(win32._PROCESSENTRY32W)]

class NativeError(RuntimeError):
    """Messages contain classifications only, never input or paths."""

def synchronized(method):
    @wraps(method)
    def guarded(self, *args, **kwargs):
        with self._guard:
            return method(self, *args, **kwargs)
    return guarded

def binaries():
    directory = Path(__file__).with_name('native')
    manifest = directory/'manifest.json'
    name = json.loads(manifest.read_text(encoding='utf-8-sig'))['observer'] if manifest.is_file() else 'TranslateObserver.dll'
    if Path(name).name!=name or not name.startswith('TranslateObserver') or not name.endswith('.dll'):
        raise NativeError('native_manifest')
    return directory/name, directory/'TranslateInject.exe'

def runtime_dll(dll):
    """Versioned per-user copy; a resident target DLL never locks the install folder."""
    data = dll.read_bytes()
    digest = hashlib.sha256(data).hexdigest()[:16]
    root = Path(os.environ.get('TRANSLATE_NATIVE_CACHE') or
                str(Path(os.environ.get('LOCALAPPDATA',tempfile.gettempdir()))/'Translate/native'))
    root.mkdir(parents=True,exist_ok=True)
    target = root/('TranslateObserver-'+digest+'.dll')
    if not target.is_file():
        temporary = root/(uuid.uuid4().hex+'.tmp')
        try:
            temporary.write_bytes(data)
            try:os.replace(temporary,target)
            except OSError:
                if not target.is_file():raise
        finally:
            temporary.unlink(missing_ok=True)
    if hashlib.sha256(target.read_bytes()).hexdigest()[:16]!=digest:
        raise NativeError('native_cache_integrity')
    return target

def find_pid():
    """Resolve a fresh process identity each reconnect, in this Windows session."""
    own = W.DWORD()
    k.ProcessIdToSessionId(os.getpid(), C.byref(own))
    snapshot = k.CreateToolhelp32Snapshot(2, 0)
    if snapshot == W.HANDLE(-1).value:
        return None
    entry = win32._PROCESSENTRY32W(dwSize=C.sizeof(win32._PROCESSENTRY32W))
    try:
        found = k.Process32FirstW(snapshot, C.byref(entry))
        while found:
            if entry.szExeFile.lower() == 'wetype_server.exe':
                session = W.DWORD()
                if k.ProcessIdToSessionId(entry.th32ProcessID, C.byref(session)) and session.value == own.value:
                    return entry.th32ProcessID
            found = k.Process32NextW(snapshot, C.byref(entry))
    finally:
        k.CloseHandle(snapshot)
    return None

class Security:
    """ACL for this user's disposable IPC objects, compatible with UIAccess tokens."""
    def __init__(self):
        a = C.WinDLL('advapi32', use_last_error=True)
        a.OpenProcessToken.argtypes = [W.HANDLE, W.DWORD, C.POINTER(W.HANDLE)]
        a.GetTokenInformation.argtypes = [W.HANDLE,W.DWORD,C.c_void_p,W.DWORD,C.POINTER(W.DWORD)]
        a.ConvertSidToStringSidW.argtypes = [C.c_void_p,C.POINTER(W.LPWSTR)]
        a.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [W.LPCWSTR,W.DWORD,C.POINTER(C.c_void_p),C.c_void_p]
        k.LocalFree.argtypes = [C.c_void_p]
        token = W.HANDLE(); needed = W.DWORD()
        if not a.OpenProcessToken(k.GetCurrentProcess(),8,C.byref(token)):
            raise NativeError('native_token')
        try:
            a.GetTokenInformation(token,1,None,0,C.byref(needed))
            buffer = C.create_string_buffer(needed.value)
            if not a.GetTokenInformation(token,1,buffer,needed,C.byref(needed)):
                raise NativeError('native_token_info')
            text = W.LPWSTR()
            if not a.ConvertSidToStringSidW(C.c_void_p.from_buffer(buffer).value,C.byref(text)):
                raise NativeError('native_sid')
            try:
                sid = text.value
            finally:
                k.LocalFree(C.cast(text,C.c_void_p))
        finally:
            k.CloseHandle(token)
        self.descriptor = C.c_void_p()
        if not a.ConvertStringSecurityDescriptorToSecurityDescriptorW(
                'D:(A;;GA;;;'+sid+')(A;;GA;;;SY)S:(ML;;NW;;;LW)',1,C.byref(self.descriptor),None):
            raise NativeError('native_security')
        class Attributes(C.Structure):
            _fields_ = [('length',W.DWORD),('descriptor',C.c_void_p),('inherit',W.BOOL)]
        self.attributes = Attributes(C.sizeof(Attributes),self.descriptor,False)
    def close(self):
        k.LocalFree(self.descriptor)

class Connection:
    def __init__(self, pid, *, allowed_foreground_pid=0, stop=None):
        self._guard = threading.RLock()
        self.pid, self.buffer, self.process = pid, None, None
        self.handles = []
        self.closed = False
        self.permits = threading.BoundedSemaphore(8)
        self.acknowledged = 0
        self.gap_pending = False
        self.received = 0
        self.security = None
        dll, injector = binaries()
        if not dll.is_file() or not injector.is_file():
            raise NativeError('native_missing')
        try:
            dll = runtime_dll(dll)
            self.atomic = C.WinDLL(str(dll.resolve()))
            self.atomic.TranslateAtomicLoad64.argtypes = [C.POINTER(C.c_int64)]
            self.atomic.TranslateAtomicLoad64.restype = C.c_int64
            self.atomic.TranslateAtomicStore64.argtypes = [C.POINTER(C.c_int64),C.c_int64]
            self.atomic.TranslateAtomicStore64.restype = None
            self.process = k.OpenProcess(0x1000|0x100000,False,pid)
            if not self.process:
                raise NativeError('native_open')
            times = [W.FILETIME() for _ in range(4)]
            if not k.GetProcessTimes(self.process,*[C.byref(v) for v in times]):
                raise NativeError('native_identity')
            birth = (times[0].dwHighDateTime<<32)|times[0].dwLowDateTime
            self.security = Security()
            sa = C.byref(self.security.attributes)
            k.CreateFileMappingW.argtypes = [W.HANDLE,C.c_void_p,W.DWORD,W.DWORD,W.DWORD,W.LPCWSTR]
            k.CreateFileMappingW.restype = W.HANDLE
            k.CreateEventW.argtypes = [C.c_void_p,W.BOOL,W.BOOL,W.LPCWSTR]
            k.CreateEventW.restype = W.HANDLE
            prefix = 'Local\\TranslateNative-'+uuid.uuid4().hex
            names = [prefix+suffix for suffix in ('-map','-data','-control')]
            mapping = k.CreateFileMappingW(W.HANDLE(-1),sa,4,0,SIZE,names[0])
            if not mapping:raise NativeError('native_mapping')
            self.handles.append(mapping)
            self.buffer = mmap.mmap(-1,SIZE,tagname=names[0])
            HEADER.pack_into(self.buffer,0,MAGIC,VERSION,SLOTS,CHUNK,0,0,0,k.GetTickCount64(),0,0,os.getpid(),allowed_foreground_pid)
            for name in names[1:]:
                handle = k.CreateEventW(sa,False,False,name)
                if not handle:raise NativeError('native_event')
                self.handles.append(handle)
            self.data_event,self.control_event = self.handles[1:]
            self.security.close(); self.security = None
            with subprocess.Popen([str(injector),str(pid),str(dll.resolve()),str(os.getpid()),*names,str(birth)],
                    stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=0x08000000) as loader:
                deadline = time.monotonic()+22
                while True:
                    if (stop is not None and stop.is_set()) or time.monotonic()>=deadline:
                        loader.kill();loader.communicate()
                        raise NativeError('native_attach_cancelled' if stop is not None and stop.is_set() else 'native_attach_timeout')
                    try:
                        output,_ = loader.communicate(timeout=.1)
                        break
                    except subprocess.TimeoutExpired:
                        pass
                returncode = loader.returncode
            try:code = json.loads(output).get('error',999)
            except (ValueError,AttributeError):code = 999
            if returncode or code:
                raise NativeError('native_attach_'+str(code))
            if self.state != RUNNING:raise NativeError('native_start')
        except BaseException:
            self.close()
            raise

    def _load64(self, offset):
        pointer = C.c_int64.from_buffer(self.buffer,offset)
        try:return self.atomic.TranslateAtomicLoad64(C.byref(pointer))
        finally:del pointer
    def _store64(self, offset, value):
        pointer = C.c_int64.from_buffer(self.buffer,offset)
        try:self.atomic.TranslateAtomicStore64(C.byref(pointer),value)
        finally:del pointer
    @property
    def state(self):
        return struct.unpack_from('<i',self.buffer,48)[0]
    @property
    @synchronized
    def healthy(self):
        return (not self.closed and self.buffer is not None and self.state==RUNNING
                and self._load64(32)==self.acknowledged
                and k.WaitForSingleObject(self.process,0)==258
                and k.GetTickCount64()-self._load64(40)<5000)
    @synchronized
    def _ack(self, generation=None):
        if generation is not None:
            self.acknowledged = generation
            self.gap_pending = False
        self.permits.release()
        if not self.closed and len(self.handles)>1:k.SetEvent(self.data_event)
    @synchronized
    def poll(self, post, epoch):
        """One bounded drain. Dispatch acknowledgements provide backpressure."""
        if self.closed or self.state!=RUNNING or k.WaitForSingleObject(self.process,0)!=258:
            raise NativeError('native_disconnected')
        self._store64(40,k.GetTickCount64())
        generation = self._load64(32)
        if generation!=self.acknowledged and not self.gap_pending and self.permits.acquire(False):
            self.gap_pending = True
            try:post({'kind':'gap','epoch':epoch,'_ack':lambda g=generation:self._ack(g)})
            except BaseException:self._ack();self.gap_pending=False;raise
        progressed = False
        for _ in range(SLOTS):
            read = self._load64(24)
            offset = HEADER.size+(read%SLOTS)*STRIDE
            if self._load64(offset)!=read+1:break
            ready,gen,handle,tick,length,reserved = SLOT.unpack_from(self.buffer,offset)
            if ready!=read+1:break
            if length>CHUNK:raise NativeError('native_packet')
            if gen!=generation or not length:
                self._store64(24,read+1);progressed=True;continue
            if generation!=self.acknowledged or self.gap_pending:break
            if not self.permits.acquire(False):break
            data = self.buffer[offset+SLOT.size:offset+SLOT.size+length]
            self._store64(24,read+1);progressed=True
            if self._load64(32)!=generation:
                self._ack();break
            self.received += 1
            try:post({'kind':'bytes','epoch':epoch,'handle':hex(handle),'data':data,'_ack':self._ack})
            except BaseException:self._ack();raise
        return progressed
    def wait(self, ms=250):
        handles = (W.HANDLE*2)(self.data_event,self.process)
        return k.WaitForMultipleObjects(2,handles,False,ms)
    @synchronized
    def close(self):
        if self.closed:return
        self.closed = True
        if self.buffer is not None and len(self.handles)==3:
            struct.pack_into('<i',self.buffer,52,1)
            k.SetEvent(self.control_event)
            until=time.monotonic()+1.5
            while self.state in (RUNNING,STOPPING) and time.monotonic()<until:
                if self.process and k.WaitForSingleObject(self.process,0)==0:break
                k.WaitForSingleObject(self.data_event,25)
        if self.buffer is not None:self.buffer.close();self.buffer=None
        for handle in reversed(self.handles):k.CloseHandle(handle)
        self.handles.clear()
        if self.process:k.CloseHandle(self.process);self.process=None
        if self.security:self.security.close();self.security=None

def run(post, stop, on_connection, *, lookup=find_pid, connect=Connection):
    """Reconnect by process identity; monotonically increasing epochs reject stale input."""
    epoch = 0
    delay = .25
    while not stop.is_set():
        epoch += 1
        connection = None
        try:
            pid = lookup()
            if pid is None:
                post({'kind':'connection','state':'waiting','epoch':epoch,'code':'not_running'})
            else:
                connection = connect(pid, stop=stop)
                if stop.is_set():
                    break
                on_connection(connection)
                post({'kind':'connection','state':'connected','epoch':epoch})
                delay = .25
                while not stop.is_set():
                    if not connection.poll(post,epoch):connection.wait()
        except Exception as error:
            # Only NativeError's fixed classification is public. No raw exception messages.
            code = str(error) if isinstance(error,NativeError) else type(error).__name__
            post({'kind':'connection','state':'waiting','epoch':epoch,'code':code})
        finally:
            if connection is not None:connection.close()
        if not stop.is_set():
            post({'kind':'connection','state':'waiting','epoch':epoch})
            stop.wait(delay)
            delay = min(delay*2,3)
