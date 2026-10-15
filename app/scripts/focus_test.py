"""Real-desktop focus and insertion test for the Electron build.

Uses real OS mouse/keyboard input (SendInput) against real target applications:
  - Tk text widget (classic Win32 window)
  - Microsoft Edge textarea (Chromium), via a throwaway profile under .cache/
and checks, after every interaction with the panel or preview, that:
  - the target is still the foreground window and its text control still has keyboard focus
  - text arrived (or did not) exactly as expected.

Run from app/:  python scripts/focus_test.py [--packaged] [--only tk|edge]
Input is only injected while the expected test window is in the foreground (see harness/win.py).
"""
from __future__ import annotations

import ctypes
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "harness"))
import win  # noqa: E402
from app import ROOT, App  # noqa: E402
import cdp  # noqa: E402

OUT = ROOT / "screenshots" / "stage3" / "focus"
OUT.mkdir(parents=True, exist_ok=True)
results: list[dict] = []


def check(target: str, name: str, ok: bool, detail: str = ""):
    results.append({"target": target, "name": name, "ok": bool(ok), "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'}  [{target}] {name}{' — ' + detail if detail else ''}", flush=True)


def shot(name: str, box: tuple[int, int, int, int]):
    try:
        from PIL import ImageGrab

        ImageGrab.grab(bbox=box, all_screens=True).save(OUT / f"{name}.png")
    except Exception as e:  # noqa: BLE001
        print("screenshot failed", e)


# ---- clipboard (saved and restored around the test) ----------------------------------------
u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
k32.GlobalLock.restype = ctypes.c_void_p
u32.GetClipboardData.restype = ctypes.c_void_p


def clip_get() -> str | None:
    for _ in range(10):
        if u32.OpenClipboard(0):
            break
        time.sleep(0.05)
    try:
        h = u32.GetClipboardData(13)
        if not h:
            return None
        p = k32.GlobalLock(ctypes.c_void_p(h))
        try:
            return ctypes.wstring_at(p)
        finally:
            k32.GlobalUnlock(ctypes.c_void_p(h))
    finally:
        u32.CloseClipboard()


def clip_set(text: str | None):
    if text is None:
        return
    subprocess.run(["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $input"], input=text, text=True, encoding="utf-8")


# ---- targets ----------------------------------------------------------------------------------
class TkTarget:
    name = "tk"

    def __init__(self):
        self.p = subprocess.Popen([sys.executable, "-X", "utf8", str(Path(__file__).parent / "harness" / "target_tk.py")], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8")
        info = json.loads(self.p.stdout.readline())
        self.hwnd, self.rect, self.text_hwnd = info["hwnd"], info["text_rect"], info["text_hwnd"]

    def text(self) -> str:
        self.p.stdin.write("get\n")
        self.p.stdin.flush()
        return json.loads(self.p.stdout.readline())["text"]

    def caret_anchor(self) -> dict:
        self.p.stdin.write("get\n")
        self.p.stdin.flush()
        c = json.loads(self.p.stdout.readline())["caret"] or [0, 0, 2, 20]
        return {"x": self.rect["x"] + c[0], "y": self.rect["y"] + c[1] + c[3] + 6, "w": 470, "h": 52}

    def focus_point(self):
        return self.rect["x"] + 200, self.rect["y"] + 40

    def has_focus(self) -> bool:
        # Tk manages keyboard focus itself; ask it which widget has focus.
        self.p.stdin.write("focus\n")
        self.p.stdin.flush()
        f = json.loads(self.p.stdout.readline())
        return win.foreground() == self.hwnd and f["focus"] == f["text"]

    def close(self):
        try:
            self.p.stdin.write("quit\n")
            self.p.stdin.flush()
            self.p.wait(3)
        except Exception:  # noqa: BLE001
            self.p.kill()


class EdgeTarget:
    name = "edge"
    PORT = 9333

    def __init__(self):
        profile = ROOT / ".cache" / "edge-test-profile"
        html = "data:text/html,<title>Translate focus target (Edge)</title><body style='margin:0'><textarea id=t autofocus style='width:100vw;height:100vh;font:16px Segoe UI;border:0;padding:12px'></textarea>"
        edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        self.p = subprocess.Popen([edge, f"--user-data-dir={profile}", f"--remote-debugging-port={self.PORT}", "--no-first-run", "--no-default-browser-check", "--disable-sync", f"--app={html}", "--window-position=120,120", "--window-size=640,260"])
        self.hwnd = 0
        for _ in range(100):
            self.hwnd = self._find()
            if self.hwnd:
                break
            time.sleep(0.1)
        time.sleep(1.0)
        r = ctypes.wintypes.RECT()
        u32.GetWindowRect(self.hwnd, ctypes.byref(r))
        self.rect = {"x": r.left + 8, "y": r.top + 40, "w": r.right - r.left - 16, "h": r.bottom - r.top - 48}

    def _find(self) -> int:
        found = []
        PROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def cb(h, _):
            buf = ctypes.create_unicode_buffer(256)
            u32.GetWindowTextW(ctypes.c_void_p(h), buf, 256)
            if "Translate focus target (Edge)" in buf.value and u32.IsWindowVisible(ctypes.c_void_p(h)):
                found.append(h)
            return True

        u32.EnumWindows(PROC(cb), 0)
        return int(found[0]) if found else 0

    def text(self) -> str:
        return cdp.evaluate(self.PORT, "document.getElementById('t').value") or ""

    def caret_anchor(self) -> dict:
        return {"x": self.rect["x"] + 20, "y": self.rect["y"] + 44, "w": 470, "h": 52}

    def focus_point(self):
        return self.rect["x"] + 300, self.rect["y"] + 30

    def has_focus(self) -> bool:
        active = cdp.evaluate(self.PORT, "document.hasFocus() && document.activeElement && document.activeElement.id")
        return win.foreground() == self.hwnd and active == "t"

    def close(self):
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(self.p.pid)], capture_output=True)


# ---- scenarios --------------------------------------------------------------------------------
def run(app: App, t) -> None:
    n = t.name
    fx, fy = t.focus_point()
    win.raise_window(t.hwnd)
    time.sleep(0.3)
    win.click(fx, fy)  # real click into the target to give it focus
    time.sleep(0.4)
    check(n, "Target has focus after a real click", t.has_focus(), f"fg={win.describe(win.foreground())}")
    win.chord("end", expected=t.hwnd)
    # Digits and spaces pass straight through any active input method (letters would start a composition).
    win.type_ascii("12 ", expected=t.hwnd)
    time.sleep(0.2)
    base = t.text()
    check(n, "Real typing reaches the target", base.endswith("12 "), repr(base[-20:]))

    def compose(scenario: str):
        app.call("/compose", {"scenario": scenario, "anchor": t.caret_anchor(), "latency": 80})
        return app.wait(lambda s: s["panel"] and s["panel"]["visible"] and s["rows"] and s["list"] and all(x == "done" for x in s["list"]["states"]), 4)

    # 1. Click a panel row → inserts, focus stays.
    s = compose("short")
    r = s["rows"][1]["phys"]
    shot(f"{n}-1-panel", (s["panel"]["phys"]["x"] - 20, s["panel"]["phys"]["y"] - 80, s["panel"]["phys"]["x"] + 420, s["panel"]["phys"]["y"] + s["panel"]["phys"]["height"] + 20))
    before = t.text()
    win.click(r["x"] + r["width"] // 2, r["y"] + r["height"] // 2, expected=t.hwnd)
    time.sleep(0.5)
    after = t.text()
    check(n, "Click on panel row inserts the translation", after == before + "event", repr(after[-20:]))
    check(n, "Focus stays in the target after clicking the panel", t.has_focus(), f"fg={win.describe(win.foreground())}")

    # 2. Alt+3 hotkey (real keyboard) → inserts #3, no stray Alt side effects.
    compose("short")
    before = t.text()
    win.chord("alt", "3", expected=t.hwnd)
    time.sleep(0.5)
    after = t.text()
    check(n, "Alt+3 inserts translation #3", after == before + "practice", repr(after[-20:]))
    check(n, "Focus stays after the Alt+3 hotkey", t.has_focus())

    # 3. Alt+Shift+2 copies without inserting.
    compose("short")
    before = t.text()
    win.chord("alt", "shift", "2", expected=t.hwnd)
    time.sleep(0.4)
    check(n, "Alt+Shift+2 copies #2 and inserts nothing", clip_get() == "event" and t.text() == before, f"clip={clip_get()!r}")
    app.call("/end")
    time.sleep(0.2)

    # 4. Lead preview: appears for a long #1; clicking/scrolling it keeps focus and inserts nothing.
    s = compose("sentence")
    s = app.wait(lambda s: s["preview"] is not None, 3)
    pv = s["preview"]["contentPhys"]
    check(n, "Lead preview appears automatically for a long #1", s["preview"]["kind"] == "outer", s["preview"]["kind"])
    shot(f"{n}-2-preview", (pv["x"] - 30, s["panel"]["phys"]["y"] - 80, pv["x"] + pv["width"] + 30, pv["y"] + pv["height"] + 30))
    before = t.text()
    win.click(pv["x"] + 60, pv["y"] + 20, expected=t.hwnd)
    time.sleep(0.4)
    check(n, "Clicking the preview body inserts nothing", t.text() == before)
    check(n, "Focus stays after clicking the preview", t.has_focus(), f"fg={win.foreground():#x}")
    win.wheel(pv["x"] + 60, pv["y"] + 20, 1, expected=t.hwnd)
    time.sleep(0.3)
    check(n, "Focus stays after scrolling the preview", t.has_focus())
    win.chord("alt", "backquote", expected=t.hwnd)
    hidden = app.wait(lambda s: s["preview"] is None, 2) is not None
    time.sleep(0.3)
    check(n, "Focus stays after Alt+` (hide)", t.has_focus(), f"fg={win.describe(win.foreground())}")
    win.chord("alt", "backquote", expected=t.hwnd)
    shown = app.wait(lambda s: s["preview"] is not None, 2) is not None
    time.sleep(0.3)
    check(n, "Alt+` hides and shows the preview", hidden and shown)
    check(n, "Focus stays after Alt+` (show)", t.has_focus(), f"fg={win.describe(win.foreground())}")
    win.chord("alt", "1", expected=t.hwnd)
    time.sleep(0.6)
    after = t.text()
    check(n, "Alt+1 inserts the full sentence", after.endswith("figures ready beforehand."), repr(after[-30:]))

    # 5. Right-click menu → Insert.
    s = compose("short")
    r = s["rows"][1]["phys"]
    cx, cy = r["x"] + 40, r["y"] + r["height"] // 2
    win.click(cx, cy, expected=t.hwnd, button="right")
    time.sleep(0.4)
    shot(f"{n}-3-context-menu", (cx - 60, cy - 60, cx + 260, cy + 120))
    before = t.text()
    win.click(cx + 40, cy + 16, expected=t.hwnd)  # first item: Insert
    time.sleep(0.5)
    after = t.text()
    check(n, "Right-click menu Insert inserts", after == before + "event", repr(after[-20:]))
    check(n, "Focus stays after using the right-click menu", t.has_focus(), f"fg={win.foreground():#x}")

    # 6. Clicks in the panel's transparent margin pass through to the app underneath.
    s = compose("short")
    p = s["panel"]["phys"]
    mx, my = p["x"] + 6, p["y"] + p["height"] // 2  # inside the 16 px margin, outside the content
    win.click(mx, my, expected=t.hwnd)
    time.sleep(0.3)
    check(n, "Click in the transparent margin reaches the target (not swallowed)", t.has_focus())
    app.call("/end")

    # 7. Unicode beyond the BMP. (The margin click above may have moved the caret; go to the end.)
    win.chord("ctrl", "end", expected=t.hwnd)
    compose("unicode")
    before = t.text()
    win.chord("alt", "1", expected=t.hwnd)
    time.sleep(0.6)
    after = t.text()
    expected = "Hello — naïve café ✓ 😀"
    check(n, "Unicode insertion (accents, symbols, emoji)", after == before + expected, repr(after[len(before):]))


def main():
    packaged = "--packaged" in sys.argv
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    saved_clip = clip_get()
    cx, cy = win.cursor()
    app = App(packaged=packaged)
    try:
        for T in (TkTarget, EdgeTarget):
            if only and T.name != only:
                continue
            t = T()
            try:
                run(app, t)
            except win.ForegroundChanged as e:
                check(T.name, "Aborted safely: foreground changed during the test", False, str(e))
            except Exception as e:  # noqa: BLE001
                check(T.name, "Unexpected error", False, repr(e)[:300])
            finally:
                app.call("/end")
                t.close()
                time.sleep(0.5)
    finally:
        app.quit()
        clip_set(saved_clip)
        win.set_cursor(cx, cy)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (OUT / f"results-{only or 'all'}-{'packaged' if packaged else 'dev'}-{stamp}.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    failed = sum(not r["ok"] for r in results)
    print(f"\n{len(results) - failed}/{len(results)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
