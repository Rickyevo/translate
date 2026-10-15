"""Flicker probe: grabs the panel's on-screen region as fast as possible while the panel should be continuously
visible, and counts frames where it is not drawn (blinks). Replay source only: synthetic candidates, no input.

Phases: (1) steady list, idle for 2 s — catches anything that fires after typing settles;
        (2) keystrokes inside one composition every 150 ms for 3 s — catches per-keystroke hide/show or blanking;
        (3) translations arriving into a shown list.
A frame "blinks" when the sampled panel pixels mostly match the desktop behind it (grabbed before the panel
appeared). Output: frames, blink frames, longest blink. Run from app/:  python -X utf8 scripts/flicker_probe.py [--dev]
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "harness"))
from app import ROOT, App  # noqa: E402
from PIL import ImageChops, ImageGrab  # noqa: E402

FG = {"hwnd": 1, "pid": 4242, "exe": "replay-target.exe"}
RECT = {"x": 900, "y": 300, "w": 470, "h": 70}


class Backdrop:
    """A black, non-activating, topmost popup of our own behind the panel area (takes no focus, gets no input).
    Shown before the panel, so the panel sits above it; if the panel stops being drawn — hidden, or dropped below
    other topmost windows — the frame shows black."""

    def __init__(self, x, y, w, h):
        import ctypes
        from ctypes import wintypes as wt
        self.u = u = ctypes.WinDLL("user32")
        u.CreateWindowExW.restype = wt.HWND
        u.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID]
        self.ready = threading.Event()
        self.tid = 0

        def run():
            self.tid = ctypes.windll.kernel32.GetCurrentThreadId()
            # WS_EX_NOACTIVATE|TOOLWINDOW|TOPMOST|TRANSPARENT (clicks pass through); WS_POPUP|WS_VISIBLE|SS_BLACKRECT
            hwnd = u.CreateWindowExW(0x08000000 | 0x80 | 0x8 | 0x20, "STATIC", "flicker-probe", 0x80000000 | 0x10000000 | 0x4, x, y, w, h, None, None, None, None)
            self.ready.set()
            msg = wt.MSG()
            while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                u.DispatchMessageW(ctypes.byref(msg))
            u.DestroyWindow(hwnd)

        threading.Thread(target=run, daemon=True).start()
        self.ready.wait(2)

    def close(self):
        self.u.PostThreadMessageW(self.tid, 0x0012, 0, 0)


def blink_stats(frames, background, box):
    blinks, longest, run = 0, 0, 0
    for f in frames:
        diff = ImageChops.difference(f, background).convert("L")
        same = sum(1 for v in diff.getdata() if v < 12) / (diff.width * diff.height)
        if same > 0.5:  # mostly the bare backdrop: the panel wasn't drawn this frame
            blinks += 1
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    return blinks, longest


def capture(box, seconds):
    frames, end = [], time.perf_counter() + seconds
    while time.perf_counter() < end:
        frames.append(ImageGrab.grab(bbox=box).convert("RGB"))
    return frames


def main() -> int:
    packaged = "--dev" not in sys.argv
    app = App(port=47391, packaged=packaged, extra_args=["--test-source=wetype-replay"])
    wt = lambda t, **f: app.call("/wetype", {"t": t, "f": f})  # noqa: E731
    out = {}
    try:
        wt("connection", state="connected")
        wt("window", rect=RECT, foreground=FG)
        # Where the panel will be: under the bar; sample an inner box of its content (no shadow edges).
        box = (RECT["x"] + 20, RECT["y"] + RECT["h"] + 4 + 20, RECT["x"] + 200, RECT["y"] + RECT["h"] + 4 + 120)
        backdrop = Backdrop(RECT["x"], RECT["y"] + RECT["h"], 300, 260)
        time.sleep(0.3)
        background = ImageGrab.grab(bbox=box).convert("RGB")
        out["backdrop_detected_before_panel"] = blink_stats([background], background, box)[0] == 1
        g = wt("bytes", steps=[{"k": "comp", "pinyin": "shi"}, {"k": "list", "words": ["时间", "事件", "实践", "世间", "试剑"]}])["gen"]
        app.wait(lambda s: s["panel"] and s["panel"]["visible"] and s["list"] and "loading" not in s["list"]["states"], 5)
        time.sleep(0.3)
        frames = capture(box, 2.0)
        out["idle_after_update"] = dict(zip(("frames", "blinks", "longest"), (len(frames), *blink_stats(frames, background, box))))

        def typing():
            for i in range(20):
                wt("bytes", steps=[{"k": "comp", "pinyin": "shi" + "j" * (i + 1)}, {"k": "list", "words": ["时间", "事件", "实践"][: 1 + i % 3] + [f"词{i}"]}])
                if i % 4 == 0:
                    wt("window", rect={**RECT, "x": RECT["x"] + (i % 8)}, foreground=FG)
                time.sleep(0.15)

        th = threading.Thread(target=typing)
        th.start()
        frames = capture(box, 3.0)
        th.join()
        out["typing_one_composition"] = dict(zip(("frames", "blinks", "longest"), (len(frames), *blink_stats(frames, background, box))))
        s = app.state()
        out["panel_hides_during_test"] = s["panelHides"]
        wt("bytes", steps=[{"k": "commit"}])
    finally:
        try:
            backdrop.close()
        except NameError:
            pass
        app.quit()
    out["build"] = "packaged" if packaged else "dev"
    print(json.dumps(out, indent=1))
    (ROOT / "measurements" / "stage5").mkdir(parents=True, exist_ok=True)
    (ROOT / "measurements" / "stage5" / f"flicker-{time.strftime('%H%M%S')}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
