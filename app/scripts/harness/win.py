"""Real input + window inspection for the focus/measurement harness (ctypes only).

Safety: every input helper takes the hwnd that must be in the foreground and refuses to inject
input otherwise, so a test can never type into a window the user switched to.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import time

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # per-monitor v2: physical pixels everywhere

ULONG_PTR = ctypes.c_size_t


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD), ("dwFlags", wt.DWORD), ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD), ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _U(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("u", _U)]


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("flags", wt.DWORD), ("hwndActive", wt.HWND), ("hwndFocus", wt.HWND), ("hwndCapture", wt.HWND), ("hwndMenuOwner", wt.HWND), ("hwndMoveSize", wt.HWND), ("hwndCaret", wt.HWND), ("rcCaret", wt.RECT)]


user32.GetForegroundWindow.restype = wt.HWND
user32.SendInput.argtypes = [wt.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.GetGUIThreadInfo.argtypes = [wt.DWORD, ctypes.POINTER(GUITHREADINFO)]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]

MOUSEEVENTF_MOVE, MOUSEEVENTF_ABSOLUTE, MOUSEEVENTF_VIRTUALDESK = 0x0001, 0x8000, 0x4000
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP, MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP, MOUSEEVENTF_WHEEL = 0x2, 0x4, 0x8, 0x10, 0x800
KEYEVENTF_KEYUP = 0x2
VK = {"space": 0x20, "backspace": 0x08, "alt": 0x12, "ctrl": 0x11, "shift": 0x10, "a": 0x41, "c": 0x43, "esc": 0x1B, "backquote": 0xC0, "down": 0x28, "up": 0x26, "pgdn": 0x22, "pgup": 0x21, "end": 0x23, "1": 0x31}
for d in range(10):
    VK[str(d)] = 0x30 + d


class ForegroundChanged(RuntimeError):
    pass


def foreground() -> int:
    return int(user32.GetForegroundWindow() or 0)


def focus_of(hwnd: int) -> int:
    pid = wt.DWORD()
    tid = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    gti = GUITHREADINFO(cbSize=ctypes.sizeof(GUITHREADINFO))
    return int(gti.hwndFocus or 0) if user32.GetGUIThreadInfo(tid, ctypes.byref(gti)) else 0


def window_pid(hwnd: int) -> int:
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def describe(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    cls = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, cls, 256)
    import psutil  # harness-only dependency

    try:
        exe = psutil.Process(window_pid(hwnd)).name()
    except Exception:  # noqa: BLE001
        exe = "?"
    return f"{hwnd:#x} '{buf.value}' class={cls.value} exe={exe}"


def guard(expected: int | None):
    if expected is not None and foreground() != expected:
        raise ForegroundChanged(f"foreground is {describe(foreground())}, expected {expected:#x}; refusing to inject input")


def _send(*inputs: INPUT):
    arr = (INPUT * len(inputs))(*inputs)
    if user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT)) != len(inputs):
        raise OSError(f"SendInput blocked (error {ctypes.get_last_error()})")


def _abs(x: int, y: int):
    vx, vy = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
    vw, vh = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
    return int((x - vx) * 65535 / (vw - 1)), int((y - vy) * 65535 / (vh - 1))


def _mouse(flags: int, x: int | None = None, y: int | None = None, data: int = 0) -> INPUT:
    dx = dy = 0
    if x is not None:
        dx, dy = _abs(x, y)
        flags |= MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
    return INPUT(type=0, u=_U(mi=MOUSEINPUT(dx, dy, data, flags, 0, 0)))


def move(x: int, y: int, expected: int | None = None, steps: int = 6):
    """Glide so hover/enter events fire like a real pointer."""
    guard(expected)
    pt = wt.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    for i in range(1, steps + 1):
        _send(_mouse(0, round(pt.x + (x - pt.x) * i / steps), round(pt.y + (y - pt.y) * i / steps)))
        time.sleep(0.012)


def click(x: int, y: int, expected: int | None = None, button: str = "left", settle: float = 0.25):
    move(x, y, expected)
    time.sleep(settle)  # hover → main stops ignoring mouse events for the panel
    guard(expected)
    down, up = (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP) if button == "left" else (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP)
    _send(_mouse(down), _mouse(up))


def wheel(x: int, y: int, notches: int, expected: int | None = None):
    move(x, y, expected)
    time.sleep(0.15)
    guard(expected)
    _send(_mouse(MOUSEEVENTF_WHEEL, data=ctypes.c_uint32(-120 * notches).value))


def key(vk: int, up: bool = False) -> INPUT:
    return INPUT(type=1, u=_U(ki=KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP if up else 0, 0, 0)))


def chord(*names: str, expected: int | None = None):
    """Press keys in order, release in reverse — a real chord like Alt+3."""
    guard(expected)
    vks = [VK[n] for n in names]
    _send(*[key(v) for v in vks], *[key(v, True) for v in reversed(vks)])


def type_ascii(text: str, expected: int | None = None):
    guard(expected)
    ev = []
    for ch in text:
        vk = user32.VkKeyScanW(ord(ch)) & 0xFF
        shift = (user32.VkKeyScanW(ord(ch)) >> 8) & 1
        if shift:
            ev.append(key(VK["shift"]))
        ev += [key(vk), key(vk, True)]
        if shift:
            ev.append(key(VK["shift"], True))
    _send(*ev)


def cursor() -> tuple[int, int]:
    pt = wt.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def set_cursor(x: int, y: int):
    user32.SetCursorPos(x, y)


def find_window(pid: int, title_part: str = "") -> int:
    found = []
    PROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

    def cb(h, _):
        if user32.IsWindowVisible(h) and window_pid(h) == pid:
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(h, buf, 256)
            if title_part in buf.value:
                found.append(int(h))
        return True

    user32.EnumWindows(PROC(cb), 0)
    return found[0] if found else 0


def raise_window(hwnd: int):
    """Bring a test window above other apps so real clicks land on it (topmost + foreground)."""
    HWND_TOPMOST, SWP_NOMOVE, SWP_NOSIZE, SWP_SHOWWINDOW = -1, 0x2, 0x1, 0x40
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    fg = foreground()
    me = kernel32.GetCurrentThreadId()
    other = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    if other and other != me:
        user32.AttachThreadInput(me, other, True)
    user32.SetForegroundWindow(hwnd)
    if other and other != me:
        user32.AttachThreadInput(me, other, False)
