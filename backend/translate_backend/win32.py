"""Thin ctypes wrappers for the Windows APIs the backend needs. No third-party dependencies.

All rectangles are in *physical* screen pixels (the process is per-monitor DPI aware v2);
the Electron host converts them to DIP with screen.screenToDipRect().
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# --- DPI -----------------------------------------------------------------------------------
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)


def enable_dpi_awareness() -> bool:
    try:
        return bool(user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2))
    except AttributeError:
        return False


# --- Foreground / focus / caret ------------------------------------------------------------
class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("flags", wt.DWORD),
        ("hwndActive", wt.HWND),
        ("hwndFocus", wt.HWND),
        ("hwndCapture", wt.HWND),
        ("hwndMenuOwner", wt.HWND),
        ("hwndMoveSize", wt.HWND),
        ("hwndCaret", wt.HWND),
        ("rcCaret", wt.RECT),
    ]


user32.GetForegroundWindow.restype = wt.HWND
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetGUIThreadInfo.argtypes = [wt.DWORD, ctypes.POINTER(GUITHREADINFO)]
user32.ClientToScreen.argtypes = [wt.HWND, ctypes.POINTER(wt.POINT)]
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
kernel32.OpenProcess.restype = wt.HANDLE
kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.CloseHandle.argtypes = [wt.HANDLE]
kernel32.GetCurrentThreadId.restype = wt.DWORD
user32.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
user32.FindWindowW.restype = wt.HWND
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
user32.GetDpiForWindow.argtypes = [wt.HWND]
user32.GetDpiForWindow.restype = wt.UINT
kernel32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def foreground() -> dict:
    """Foreground window, its process and the focused control (when visible to us)."""
    hwnd = user32.GetForegroundWindow()
    pid = wt.DWORD()
    tid = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid)) if hwnd else 0
    info = {"hwnd": int(hwnd or 0), "pid": int(pid.value), "exe": process_exe(pid.value) if pid.value else ""}
    gti = GUITHREADINFO(cbSize=ctypes.sizeof(GUITHREADINFO))
    if tid and user32.GetGUIThreadInfo(tid, ctypes.byref(gti)):
        info["focus"] = int(gti.hwndFocus or 0)
        info["password"] = bool(gti.hwndFocus and user32.GetWindowLongW(gti.hwndFocus, -16) & 0x20)
        if gti.hwndCaret:
            tl = wt.POINT(gti.rcCaret.left, gti.rcCaret.top)
            br = wt.POINT(gti.rcCaret.right, gti.rcCaret.bottom)
            user32.ClientToScreen(gti.hwndCaret, ctypes.byref(tl))
            user32.ClientToScreen(gti.hwndCaret, ctypes.byref(br))
            info["caret"] = {"x": tl.x, "y": tl.y, "w": max(1, br.x - tl.x), "h": br.y - tl.y}
    return info


def process_exe(pid: int) -> str:
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        size = wt.DWORD(1024)
        buf = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value)
        return ""
    finally:
        kernel32.CloseHandle(h)


def window_rect(hwnd: int) -> dict | None:
    r = wt.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
        return None
    return {"x": r.left, "y": r.top, "w": r.right - r.left, "h": r.bottom - r.top}


# --- WeType candidate bar --------------------------------------------------------------------
# WeType draws its bar somewhere inside a large transparent Flutter canvas (628×314 at 96 dpi). Where depends on the
# WeType version, its layout settings (pinyin above the candidates or inline), the DPI and whether the canvas had to
# flip near a screen edge; the IME's messages don't say. So the bar is found where it is actually drawn: the canvas
# window alone is rendered into memory (PrintWindow, PW_RENDERFULLCONTENT — only WeType's own pixels, never the
# screen or other windows) and the box of drawn pixels is taken. Transparent parts render black. Nothing is kept:
# only the four numbers of the box. ~8 ms; cached for 50 ms per window.
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
user32.GetDC.restype = wt.HDC
user32.GetDC.argtypes = [wt.HWND]
user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
user32.PrintWindow.argtypes = [wt.HWND, wt.HDC, wt.UINT]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateDIBSection.restype = wt.HBITMAP
gdi32.CreateDIBSection.argtypes = [wt.HDC, ctypes.c_void_p, wt.UINT, ctypes.POINTER(ctypes.c_void_p), wt.HANDLE, wt.DWORD]
gdi32.SelectObject.restype = wt.HGDIOBJ
gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wt.HDC]


class _BIH(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
                ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
                ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]


PW_RENDERFULLCONTENT = 2
_INK = bytes(1 if i > 24 else 0 for i in range(256))  # "drawn": any colour channel above near-black
BAR_TTL_S = 0.05
_bar_cache: dict[int, tuple[float, tuple[int, int], tuple[int, int, int, int] | None]] = {}
_bar_last: dict[tuple[int, int, int], tuple[int, int, int, int]] = {}  # (w, h, dpi) → last good box


def _render(hwnd: int, w: int, h: int) -> bytes | None:
    sdc = user32.GetDC(None)
    mdc = gdi32.CreateCompatibleDC(sdc)
    bits = ctypes.c_void_p()
    bmp = gdi32.CreateDIBSection(mdc, ctypes.byref(_BIH(ctypes.sizeof(_BIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)), 0, ctypes.byref(bits), None, 0)
    try:
        if not bmp or not bits.value:
            return None
        old = gdi32.SelectObject(mdc, bmp)
        ok = user32.PrintWindow(hwnd, mdc, PW_RENDERFULLCONTENT)
        data = ctypes.string_at(bits.value, w * h * 4) if ok else None
        gdi32.SelectObject(mdc, old)
        return data
    finally:
        if bmp:
            gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mdc)
        user32.ReleaseDC(None, sdc)


def ink_bbox(buf: bytes, w: int, h: int) -> tuple[int, int, int, int] | None:
    """(x, y, w, h) of the pixels that are not (near) black in a 32-bit BGRA buffer, or None."""
    planes = [bytes(buf[i::4]).translate(_INK) for i in (0, 1, 2)]
    top = bottom = left = right = None
    for y in range(h):
        s, e = y * w, (y + 1) * w
        firsts = [i for i in (p.find(b"", s, e) for p in planes) if i >= 0]
        if not firsts:
            continue
        r = max(p.rfind(b"", s, e) for p in planes)
        top = y if top is None else top
        bottom = y
        left = min(firsts) - s if left is None else min(left, min(firsts) - s)
        right = r - s if right is None else max(right, r - s)
    return None if top is None else (left, top, right - left + 1, bottom - top + 1)


def plausible_bar(box, w: int, h: int, scale: float) -> bool:
    if not box:
        return False
    _, _, bw, bh = box
    return bw >= 80 * scale and 16 * scale <= bh <= h * 0.8 and not (bw >= w - 2 and bh >= h - 2)


def wetype_bar(hwnd: int, rect: dict, scale: float) -> tuple[tuple[int, int, int, int], bool]:
    """The drawn bar inside the canvas, relative to it: ((x, y, w, h), measured)."""
    import time
    size = (rect["w"], rect["h"])
    now = time.monotonic()
    hit = _bar_cache.get(hwnd)
    if hit and hit[1] == size and now - hit[0] < BAR_TTL_S and hit[2]:
        return hit[2], True
    box = None
    try:
        buf = _render(hwnd, *size)
        box = ink_bbox(buf, *size) if buf else None
    except Exception:  # noqa: BLE001 — fall back below
        box = None
    key = (size[0], size[1], round(scale * 96))
    if plausible_bar(box, size[0], size[1], scale):
        _bar_cache[hwnd] = (now, size, box)
        _bar_last[key] = box
        return box, True
    _bar_cache.pop(hwnd, None)
    if key in _bar_last:
        return _bar_last[key], False
    # Never measured at this size: the full-width band WeType 2.1/3.0 use in their default layout.
    return (0, round(109 * scale), size[0], min(round(70 * scale), size[1] - round(109 * scale))), False


def wetype_candidate_rect(hwnd: int | None = None) -> dict | None:
    """WeType's candidate *bar* (where it is drawn), plus "canvas": its whole transparent window.

    "measured" is False when the bar couldn't be found in the window's pixels (e.g. not drawn yet) and the last
    known or default position was used; callers sample again shortly after.
    """
    hwnd = hwnd if hwnd is not None else user32.FindWindowW(None, "wetype_candidate")
    if not hwnd or not user32.IsWindowVisible(hwnd):
        return None
    rect = window_rect(hwnd)
    if not rect or rect["w"] <= 0 or rect["h"] <= 0:
        return None
    scale = (user32.GetDpiForWindow(hwnd) or 96) / 96
    (bx, by, bw, bh), measured = wetype_bar(hwnd, rect, scale)
    if bh <= 0:
        return None
    # "canvas": the whole IME window. It runs with UIAccess (z-band above every normal window) and takes all
    # mouse input over its area, transparent parts included; the host can place the panel clear of it.
    return {"x": rect["x"] + bx, "y": rect["y"] + by, "w": bw, "h": bh, "canvas": rect, "measured": measured}


def wetype_candidate_hwnd() -> int:
    return int(user32.FindWindowW(None, "wetype_candidate") or 0)


def window_pid(hwnd: int) -> int:
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


# --- WinEvent hooks (event-driven window tracking; no polling) -----------------------------------
EVENT_SYSTEM_FOREGROUND = 0x0003
EVENT_OBJECT_SHOW = 0x8002
EVENT_OBJECT_HIDE = 0x8003
EVENT_OBJECT_FOCUS = 0x8005
EVENT_OBJECT_LOCATIONCHANGE = 0x800B
WINEVENT_OUTOFCONTEXT = 0x0000
WINEVENT_SKIPOWNPROCESS = 0x0002
OBJID_WINDOW = 0
WM_TIMER = 0x0113
WM_QUIT = 0x0012

WINEVENTPROC = ctypes.WINFUNCTYPE(None, wt.HANDLE, wt.DWORD, wt.HWND, wt.LONG, wt.LONG, wt.DWORD, wt.DWORD)
user32.SetWinEventHook.argtypes = [wt.DWORD, wt.DWORD, wt.HMODULE, WINEVENTPROC, wt.DWORD, wt.DWORD, wt.DWORD]
user32.SetWinEventHook.restype = wt.HANDLE
user32.UnhookWinEvent.argtypes = [wt.HANDLE]
user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
user32.PostThreadMessageW.argtypes = [wt.DWORD, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.SetTimer.argtypes = [wt.HWND, ctypes.c_size_t, wt.UINT, ctypes.c_void_p]
user32.SetTimer.restype = ctypes.c_size_t


class WindowEvents:
    """Calls `on_event()` (on this watcher's own thread) when the foreground window or keyboard focus changes
    anywhere, or when a window of the target process is shown, hidden or moved. The target process is
    resolved by `find_hwnd()` and re-resolved every `rescan_ms` (cheap; covers the IME restarting).
    Sleeps in GetMessage between events. Metadata only: no text, no keyboard hooks."""

    def __init__(self, find_hwnd, on_event, rescan_ms: int = 2000, flags: int = WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS):
        self._find, self._on_event, self._rescan, self._flags = find_hwnd, on_event, rescan_ms, flags
        self._proc = WINEVENTPROC(self._callback)  # keep a reference for the hooks' lifetime
        self._tid = 0
        self._target_pid = 0
        self._target_hook = None
        self.target_hwnd = 0

    def _callback(self, hook, event, hwnd, id_object, id_child, thread, time_ms):
        if event in (EVENT_SYSTEM_FOREGROUND, EVENT_OBJECT_FOCUS):
            self._on_event()
        elif id_object == OBJID_WINDOW and id_child == 0 and int(hwnd or 0) == self.target_hwnd:
            self._on_event()

    def _retarget(self) -> None:
        hwnd = self._find()
        pid = window_pid(hwnd) if hwnd else 0
        changed = hwnd != self.target_hwnd
        self.target_hwnd = hwnd
        if pid != self._target_pid:
            if self._target_hook:
                user32.UnhookWinEvent(self._target_hook)
                self._target_hook = None
            self._target_pid = pid
            if pid:
                self._target_hook = user32.SetWinEventHook(EVENT_OBJECT_SHOW, EVENT_OBJECT_LOCATIONCHANGE, None, self._proc, pid, 0, self._flags)
        if changed:
            self._on_event()

    def run(self) -> None:
        """Blocking message loop; returns after stop()."""
        self._tid = kernel32.GetCurrentThreadId()
        hooks = [user32.SetWinEventHook(e, e, None, self._proc, 0, 0, self._flags) for e in (EVENT_SYSTEM_FOREGROUND, EVENT_OBJECT_FOCUS)]
        self._retarget()
        self._on_event()
        user32.SetTimer(None, 0, self._rescan, None)
        msg = wt.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_TIMER:
                    self._retarget()
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            for h in hooks + ([self._target_hook] if self._target_hook else []):
                user32.UnhookWinEvent(h)

    def stop(self) -> None:
        if self._tid:
            user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)


# --- Input -----------------------------------------------------------------------------------
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_ESCAPE = 0x1B
ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD), ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD), ("dwFlags", wt.DWORD), ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("u", _INPUTUNION)]


user32.SendInput.argtypes = [wt.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wt.UINT

# Tag our injected input so hooks (ours, later) can ignore it.
INJECT_TAG = 0x7472616E  # 'tran'


def _key(vk: int = 0, scan: int = 0, flags: int = 0) -> INPUT:
    return INPUT(type=INPUT_KEYBOARD, u=_INPUTUNION(ki=KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=INJECT_TAG)))


def send_unicode(text: str) -> int:
    """Type text into whatever has keyboard focus, as Unicode key events (any script, incl. surrogates).

    Returns the number of events Windows accepted. UIPI blocks input into elevated windows: in that
    case SendInput reports fewer events than requested and GetLastError is set.
    """
    units = text.encode("utf-16-le")
    events: list[INPUT] = []
    for i in range(0, len(units), 2):
        code = int.from_bytes(units[i : i + 2], "little")
        if code == 0x0A:  # newline → Enter so editors create a line break
            events += [_key(vk=0x0D), _key(vk=0x0D, flags=KEYEVENTF_KEYUP)]
            continue
        events += [_key(scan=code, flags=KEYEVENTF_UNICODE), _key(scan=code, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)]
    if not events:
        return 0
    arr = (INPUT * len(events))(*events)
    return int(user32.SendInput(len(events), arr, ctypes.sizeof(INPUT)))


def send_key(vk: int) -> int:
    arr = (INPUT * 2)(_key(vk=vk), _key(vk=vk, flags=KEYEVENTF_KEYUP))
    return int(user32.SendInput(2, arr, ctypes.sizeof(INPUT)))


def modifiers_down() -> list[str]:
    """Physical modifier state — insertion waits for Alt to be released so text isn't read as accelerators."""
    names = {0x10: "shift", 0x11: "ctrl", 0x12: "alt", 0x5B: "win", 0x5C: "win"}
    return sorted({n for vk, n in names.items() if user32.GetAsyncKeyState(vk) & 0x8000})
