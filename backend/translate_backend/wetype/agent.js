/*
 * Translate — WeType observation agent (injected into wetype_server.exe by Frida).
 *
 * Observes NtWriteFile on WeType session_v2/server_for_renderer pipes and forwards the
 * written bytes to the host. Read-only by construction:
 *   - the original WriteFile always runs first; we only look at the buffer in onLeave
 *   - arguments and return values are never modified, nothing blocks
 *   - non-pipe handles are rejected with one cheap GetFileType call, then cached
 *   - any error is counted; after ERR_LIMIT consecutive errors the hook becomes a pure pass-through
 *   - parsing happens in the host, never inside the IME process
 */
'use strict';

const TARGET = 'session_v2';
const MAX_FORWARD = 262144; // bytes per write
const ERR_LIMIT = 20;
const CACHE_MS = 5000; // handle → verdict cache lifetime (handles get reused after reconnects)

const k32 = Process.getModuleByName('kernel32.dll');
// NtWriteFile is the single user-mode path under WriteFile/WriteFileEx/overlapped writes.
const NtWriteFile = Process.getModuleByName('ntdll.dll').getExportByName('NtWriteFile');
const getFileType = new NativeFunction(k32.getExportByName('GetFileType'), 'uint32', ['pointer']);
const getInfo = new NativeFunction(k32.getExportByName('GetFileInformationByHandleEx'), 'int', ['pointer', 'int', 'pointer', 'uint32']);
const FILE_TYPE_PIPE = 3;
const FileNameInfo = 2;
const nameBuf = Memory.alloc(2048);

let disabled = false;
let errors = 0;
let seq = 0;
const cache = new Map(); // handle string → { ok, t }

function isTarget(h) {
  const key = h.toString();
  const now = Date.now();
  const c = cache.get(key);
  if (c && now - c.t < CACHE_MS) return c.ok;
  let ok = false;
  let name = '';
  if (getFileType(h) === FILE_TYPE_PIPE && getInfo(h, FileNameInfo, nameBuf, 2048)) {
    const bytes = Math.min(nameBuf.readU32(), 2044);
    name = nameBuf.add(4).readUtf16String(bytes / 2) || '';
    ok = name.indexOf(TARGET) >= 0 || name.indexOf('server_for_renderer') >= 0;
  }
  cache.set(key, { ok: ok, t: now });
  if (cache.size > 512) cache.delete(cache.keys().next().value);
  return ok;
}

// NtWriteFile(FileHandle, Event, ApcRoutine, ApcContext, IoStatusBlock, Buffer, Length, ByteOffset, Key)
// The buffer holds the outgoing bytes at call time (also for asynchronous writes), so we copy it in
// onEnter and send it after the call returned with a non-error status.
Interceptor.attach(NtWriteFile, {
  onEnter(args) {
    this.data = null;
    if (disabled) return;
    try {
      const h = args[0];
      if (!isTarget(h)) return;
      const n = Math.min(args[6].toUInt32(), MAX_FORWARD);
      if (n === 0) return;
      this.h = h.toString();
      this.n = n;
      this.data = args[5].readByteArray(n);
    } catch (e) {
      fail(e);
    }
  },
  onLeave(ret) {
    if (!this.data) return;
    const status = ret.toUInt32();
    // STATUS_SUCCESS (0) or STATUS_PENDING (0x103): the write went (or is going) out.
    if (status !== 0 && status !== 0x103) return;
    try {
      send({ t: 'w', seq: ++seq, handle: this.h, len: this.n }, this.data);
      errors = 0;
    } catch (e) {
      fail(e);
    }
  },
});

function fail(e) {
  if (++errors >= ERR_LIMIT) {
    disabled = true;
    send({ t: 'disabled', error: String(e) });
  }
}

rpc.exports = {
  stats() {
    return { seq: seq, errors: errors, disabled: disabled, handles: cache.size };
  },
};

send({ t: 'ready', pid: Process.id });
