"""Controlled capture session: types pinyin into our own Tk test window (real keyboard input via
SendInput, WeChat IME active) while wetype_capture.py records pipe traffic and window events.

Run from backend/:  python -X utf8 tools/wetype_session.py OUTDIR
Input goes only to the test window (foreground-guarded; aborts otherwise).
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "app" / "scripts" / "harness"))
import win  # noqa: E402

out = Path(sys.argv[1] if len(sys.argv) > 1 else HERE.parents[1] / ".cache" / "wetype")
out.mkdir(parents=True, exist_ok=True)
marks = open(out / "marks.jsonl", "w", encoding="utf-8")


def mark(what):
    marks.write(json.dumps({"wall": time.time(), "mark": what}, ensure_ascii=False) + "\n")
    marks.flush()
    print("·", what, flush=True)


tk = subprocess.Popen([sys.executable, "-X", "utf8", str(HERE.parents[1] / "app" / "scripts" / "harness" / "target_tk.py")], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8")
info = json.loads(tk.stdout.readline())
hwnd, rect = info["hwnd"], info["text_rect"]
cap = subprocess.Popen([sys.executable, "-X", "utf8", str(HERE / "wetype_capture.py"), "45", str(out / "capture.jsonl"), "--broad", f"--only-hwnd={hwnd}"])
time.sleep(3)

try:
    win.raise_window(hwnd)
    time.sleep(0.3)
    win.click(rect["x"] + 200, rect["y"] + 40)
    time.sleep(0.5)
    win.guard(hwnd)

    def keys(text, gap=0.12, label=None):
        mark(label or f"type {text}")
        for ch in text:
            win.type_ascii(ch, expected=hwnd)
            time.sleep(gap)

    def press(*names, label):
        mark(label)
        win.chord(*names, expected=hwnd)

    import ctypes
    from PIL import ImageGrab

    def snap(name):
        h = ctypes.windll.user32.FindWindowW(None, "wetype_candidate")
        r = ctypes.wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(h, ctypes.byref(r))
        ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom), all_screens=True).save(out / f"cand-{name}.png")
        mark(f"snap {name} rect={[r.left, r.top, r.right - r.left, r.bottom - r.top]}")

    keys("nihao")
    time.sleep(1.0)
    snap("nihao")
    press("space", label="space (commit)")
    time.sleep(1.0)
    keys("shijian")
    time.sleep(1.0)
    snap("shijian")
    press("2", label="digit 2 (commit)")
    time.sleep(1.0)
    keys("womenmingtianxiawusandian", gap=0.08, label="type long")
    time.sleep(1.2)
    snap("long")
    press("esc", label="esc (cancel)")
    time.sleep(1.0)
    mark("done")
finally:
    time.sleep(1)
    cap.wait(timeout=80)
    tk.stdin.write("get\n")
    tk.stdin.flush()
    print("target text:", json.loads(tk.stdout.readline())["text"])
    tk.stdin.write("quit\n")
    tk.stdin.flush()
