"""Hybrid translation cache.

Memory (this session only): every translation, LRU, 2,000 entries. Gone when Translate quits.
Disk (persists): only reusable vocabulary — a candidate of 1–4 Chinese characters that is itself a CC-CEDICT headword
(general dictionary vocabulary, not something only the user would type), with a short translation from the service.
Anything longer, anything with digits, Latin letters or symbols, and anything not in the dictionary (personal names,
made-up phrases, account names) stays in memory only. The file is encrypted with Windows DPAPI for the current user
(CryptProtectData), capped at 20,000 entries (least recently used dropped), and written a few seconds after changes
and at exit. Never logged.
"""
from __future__ import annotations

import collections
import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import threading
from pathlib import Path

MEMORY_MAX = 2000
DISK_MAX = 20000
HAN = re.compile(r"^[㐀-䶿一-鿿豈-﫿]{1,4}$")


class _BLOB(ctypes.Structure):
    _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


_crypt = ctypes.WinDLL("crypt32", use_last_error=True)
_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_crypt.CryptProtectData.argtypes = [ctypes.POINTER(_BLOB), wt.LPCWSTR, ctypes.POINTER(_BLOB), ctypes.c_void_p, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(_BLOB)]
_crypt.CryptUnprotectData.argtypes = [ctypes.POINTER(_BLOB), ctypes.c_void_p, ctypes.POINTER(_BLOB), ctypes.c_void_p, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(_BLOB)]
_k32.LocalFree.argtypes = [ctypes.c_void_p]
_ENTROPY = b"Translate translation cache v1"
CRYPTPROTECT_UI_FORBIDDEN = 0x1


def _blob(data: bytes) -> _BLOB:
    buf = ctypes.create_string_buffer(data, len(data))
    b = _BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    b._buf = buf  # keep alive
    return b


def protect(data: bytes) -> bytes:
    out = _BLOB()
    if not _crypt.CryptProtectData(ctypes.byref(_blob(data)), None, ctypes.byref(_blob(_ENTROPY)), None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out)):
        raise OSError("CryptProtectData failed")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        _k32.LocalFree(out.pbData)


def unprotect(data: bytes) -> bytes:
    out = _BLOB()
    if not _crypt.CryptUnprotectData(ctypes.byref(_blob(data)), None, ctypes.byref(_blob(_ENTROPY)), None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out)):
        raise OSError("CryptUnprotectData failed")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        _k32.LocalFree(out.pbData)


def persistable(text: str, translation: str, is_headword) -> bool:
    return bool(HAN.match(text)) and 0 < len(translation) <= 60 and "\n" not in translation and is_headword(text)


class Cache:
    def __init__(self, is_headword):
        self._is_headword = is_headword
        self._mem: collections.OrderedDict = collections.OrderedDict()
        self._disk: collections.OrderedDict = collections.OrderedDict()
        self._path: Path | None = None
        self._dirty = False
        self._lock = threading.Lock()  # the save runs on the scheduler thread

    # ---- lookups (dispatch thread) ---------------------------------------------------------
    def get(self, target: str, text: str) -> str | None:
        k = target + "\x1f" + text
        v = self._mem.get(k)
        if v is not None:
            self._mem.move_to_end(k)
            return v
        with self._lock:
            v = self._disk.get(k)
            if v is not None:
                self._disk.move_to_end(k)
        return v

    def put(self, target: str, text: str, translation: str) -> None:
        k = target + "\x1f" + text
        self._mem[k] = translation
        self._mem.move_to_end(k)
        while len(self._mem) > MEMORY_MAX:
            self._mem.popitem(last=False)
        if self._path is not None and persistable(text, translation, self._is_headword):
            with self._lock:
                self._disk[k] = translation
                self._disk.move_to_end(k)
                while len(self._disk) > DISK_MAX:
                    self._disk.popitem(last=False)
                self._dirty = True

    # ---- persistence ------------------------------------------------------------------------
    def open(self, directory: str) -> None:
        path = Path(directory) / "cache" / "translations.bin"
        if self._path == path:
            return
        self._path = path
        try:
            data = json.loads(unprotect(path.read_bytes()).decode("utf-8"))
            with self._lock:
                self._disk = collections.OrderedDict((k, v) for k, v in data.items() if isinstance(v, str))
        except FileNotFoundError:
            pass
        except Exception:  # noqa: BLE001 — unreadable (other user, corrupt): start empty, overwrite on next save
            with self._lock:
                self._disk.clear()

    def save(self) -> None:
        with self._lock:
            if not self._dirty or self._path is None:
                return
            payload = json.dumps(self._disk, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self._dirty = False
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_bytes(protect(payload))
        os.replace(tmp, self._path)

    @property
    def dirty(self) -> bool:
        return self._dirty

    def stats(self) -> dict:
        size = self._path.stat().st_size if self._path and self._path.exists() else 0
        return {"count": len(self._disk), "bytes": size, "memory": len(self._mem)}

    def clear(self) -> None:
        self._mem.clear()
        with self._lock:
            self._disk.clear()
            self._dirty = False
        if self._path and self._path.exists():
            self._path.unlink()
