"""API keys and tokens in Windows Credential Manager (generic credentials, this user, this PC).

Keys arrive from the host only (config channel), are read here when a request is made, and are never logged or sent
back. TRANSLATE_SECRETS=memory (tests) keeps them in process memory instead of touching the user's vault.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os

PREFIX = "Translate:service:"
CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2
ERROR_NOT_FOUND = 1168


class CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ("Flags", wt.DWORD), ("Type", wt.DWORD), ("TargetName", wt.LPWSTR), ("Comment", wt.LPWSTR),
        ("LastWritten", wt.FILETIME), ("CredentialBlobSize", wt.DWORD), ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wt.DWORD), ("AttributeCount", wt.DWORD), ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wt.LPWSTR), ("UserName", wt.LPWSTR),
    ]


_adv = ctypes.WinDLL("advapi32", use_last_error=True)
_adv.CredWriteW.argtypes = [ctypes.POINTER(CREDENTIALW), wt.DWORD]
_adv.CredReadW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.POINTER(ctypes.POINTER(CREDENTIALW))]
_adv.CredDeleteW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD]
_adv.CredFree.argtypes = [ctypes.c_void_p]

_memory: dict[str, str] | None = {} if os.environ.get("TRANSLATE_SECRETS") == "memory" else None


def _target(provider: str) -> str:
    return PREFIX + provider


def set_key(provider: str, key: str) -> bool:
    """Store (or, with an empty key, delete) the credential for a provider."""
    key = key.strip()
    if _memory is not None:
        if key:
            _memory[provider] = key
        else:
            _memory.pop(provider, None)
        return True
    if not key:
        ok = _adv.CredDeleteW(_target(provider), CRED_TYPE_GENERIC, 0)
        return bool(ok) or ctypes.get_last_error() == ERROR_NOT_FOUND
    blob = key.encode("utf-16-le")
    buf = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
    cred = CREDENTIALW(Type=CRED_TYPE_GENERIC, TargetName=_target(provider), CredentialBlobSize=len(blob),
                       CredentialBlob=ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)), Persist=CRED_PERSIST_LOCAL_MACHINE,
                       UserName="Translate")
    return bool(_adv.CredWriteW(ctypes.byref(cred), 0))


def get_key(provider: str) -> str:
    if _memory is not None:
        return _memory.get(provider, "")
    p = ctypes.POINTER(CREDENTIALW)()
    if not _adv.CredReadW(_target(provider), CRED_TYPE_GENERIC, 0, ctypes.byref(p)):
        return ""
    try:
        c = p.contents
        return bytes(c.CredentialBlob[: c.CredentialBlobSize]).decode("utf-16-le")
    finally:
        _adv.CredFree(p)


def has_key(provider: str) -> bool:
    return bool(get_key(provider))
