"""LIVE: panel placement with the real WeChat Input Method near screen edges — this script types.

Opens its own test windows — a classic Win32 text box (Tk: system caret) and an Edge text area (Chromium: accessibility
caret) — at the middle, the top edge, the bottom edge (WeType keeps its bar below the caret), the very bottom (WeType
has to flip its bar above the caret) and the bottom-right corner of the screen. In each it clicks into the text,
types pinyin with real key presses, and checks: candidates arrive, the panel shows, it does not cover WeType's bar or
the typing line, and it stays inside the work area. Esc cancels each composition. Input only ever goes to its own
windows: if another window comes to the front, it stops without sending anything.

Privacy: positions, generations and counts only — never candidate or typed text.
Prerequisites: WeType is the active input method in Chinese mode; quit your own Translate; don't touch the PC
(about 2 minutes). Run from app/:  python -X utf8 scripts/live_edge_test.py [Translate.exe]
"""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import time
import urllib.request
from ctypes import wintypes as wt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "harness"))
import win  # noqa: E402
from app import PACKAGED, ROOT  # noqa: E402

PORT = 47521
EDGE_CDP = 9334
EXE = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else PACKAGED
USERDATA = ROOT / ".cache" / "live-edge-userdata"
u32 = ctypes.windll.user32
results: list[dict] = []


def check(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": detail})
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""), flush=True)
    return bool(ok)


def state():
    with urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{PORT}/state", data=b"{}", method="POST"), timeout=3) as r:
        return json.loads(r.read())


def wait(pred, timeout=4.0, step=0.04):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            s = state()
            if pred(s):
                return s
        except Exception:  # noqa: BLE001
            pass
        time.sleep(step)
    return None


def work_area():
    r = wt.RECT()
    u32.SystemParametersInfoW(0x30, 0, ctypes.byref(r), 0)
    return {"x": r.left, "y": r.top, "w": r.right - r.left, "h": r.bottom - r.top}


def overlap(a, b):
    return a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"] and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]


def inside(a, w):
    return a["x"] >= w["x"] and a["y"] >= w["y"] and a["x"] + a["w"] <= w["x"] + w["w"] and a["y"] + a["h"] <= w["y"] + w["h"]


class Tk:
    name = "Tk (Win32 caret)"

    def __init__(self, x, y, w, h):
        env = {**os.environ, "TARGET_GEOMETRY": f"{w}x{h}+{x}+{y}"}
        self.p = subprocess.Popen([sys.executable, "-X", "utf8", str(Path(__file__).parent / "harness" / "target_tk.py")], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8", env=env)
        info = json.loads(self.p.stdout.readline())
        self.hwnd, self.rect = info["hwnd"], info["text_rect"]
        time.sleep(0.5)

    def click_point(self):
        return self.rect["x"] + 60, self.rect["y"] + 14

    def caret(self):
        """The real caret line from the widget itself (screen px), independent of what the app reports to Windows."""
        self.p.stdin.write("get\n")
        self.p.stdin.flush()
        c = json.loads(self.p.stdout.readline())["caret"]
        return {"x": self.rect["x"] + c[0], "y": self.rect["y"] + c[1], "w": max(2, c[2]), "h": c[3]} if c else None

    def clear(self):
        self.p.stdin.write("clear\n")
        self.p.stdin.flush()
        self.p.stdout.readline()

    def close(self):
        try:
            self.p.stdin.write("quit\n")
            self.p.stdin.flush()
            self.p.wait(3)
        except Exception:  # noqa: BLE001
            self.p.kill()


class Edge:
    name = "Edge (accessibility caret)"

    seq = 0

    def __init__(self, x, y, w, h):
        Edge.seq += 1
        self.title = f"Translate edge target {Edge.seq}"
        profile = ROOT / ".cache" / "edge-test-profile"
        html = (f"data:text/html,<title>{self.title}</title><body style='margin:0;overflow:hidden'>"
                "<textarea id=t autofocus style='width:100vw;height:100vh;font:16px Segoe UI;border:0;padding:8px 12px;resize:none'></textarea>")
        edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        self.p = subprocess.Popen([edge, f"--user-data-dir={profile}", f"--remote-debugging-port={EDGE_CDP}", "--no-first-run", "--no-default-browser-check",
                                   "--disable-sync", "--force-renderer-accessibility", f"--app={html}", f"--window-position={x},{y}", f"--window-size={w},{h}"])
        self.hwnd = 0
        for _ in range(150):
            self.hwnd = self._find()
            if self.hwnd:
                break
            time.sleep(0.1)
        time.sleep(1.5)
        # Keep our own test window above others (as the Tk one), so another window can't cover the click point.
        u32.SetWindowPos(wt.HWND(self.hwnd), wt.HWND(-1), 0, 0, 0, 0, 0x0003)
        r = wt.RECT()
        u32.GetWindowRect(self.hwnd, ctypes.byref(r))
        self.win = {"x": r.left, "y": r.top, "w": r.right - r.left, "h": r.bottom - r.top}

    def _find(self):
        found = []

        @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
        def cb(h, _):
            buf = ctypes.create_unicode_buffer(256)
            u32.GetWindowTextW(h, buf, 256)
            if buf.value == self.title and u32.IsWindowVisible(h):
                found.append(h)
            return True

        u32.EnumWindows(cb, 0)
        return found[0] if found else 0

    def click_point(self):
        return self.win["x"] + 80, self.win["y"] + self.win["h"] // 2

    def caret(self):
        return None  # judged against the caret the app reports (and the bar)

    def text_len(self) -> int:
        import cdp
        try:
            return int(cdp.evaluate(EDGE_CDP, "document.getElementById('t').value.length", "data:text/html"))
        except Exception:  # noqa: BLE001
            return -1

    def typed_raw(self) -> bool:
        """Letters landed in the text area as plain text: the IME wasn't composing (English mode)."""
        import cdp
        try:
            return bool(cdp.evaluate(EDGE_CDP, "/^[a-z]+$/.test(document.getElementById('t').value)", "data:text/html"))
        except Exception:  # noqa: BLE001
            return False

    def clear(self):
        import cdp
        try:
            cdp.evaluate(EDGE_CDP, "document.getElementById('t').value=''")
        except Exception:  # noqa: BLE001
            pass

    def close(self):
        # Close the whole browser (a plain terminate leaves its window open, and the next launch would hand off to it).
        import cdp
        try:
            url = json.load(urllib.request.urlopen(f"http://127.0.0.1:{EDGE_CDP}/json/version", timeout=3))["webSocketDebuggerUrl"]
            s = cdp._ws_connect(url)
            cdp._send(s, json.dumps({"id": 1, "method": "Browser.close"}))
            s.close()
        except Exception:  # noqa: BLE001
            pass
        for _ in range(50):
            if not self._find():
                break
            time.sleep(0.1)
        try:
            self.p.wait(5)
        except subprocess.TimeoutExpired:
            self.p.kill()


def run_case(target, label, wa, pinyin="shijian"):
    tag = f"{target.name} · {label}"
    x, y = target.click_point()
    u32.WindowFromPoint.restype = wt.HWND
    u32.GetAncestor.restype = wt.HWND
    under = u32.GetAncestor(u32.WindowFromPoint(wt.POINT(x, y)), 2) or 0
    if under != target.hwnd:
        return check(f"{tag}: test window under the click point", False, "another window covers it; nothing clicked or typed")
    win.click(x, y, expected=None)
    time.sleep(0.4)
    if win.foreground() != target.hwnd:
        return check(f"{tag}: test window in front", False, "another window is in front; nothing typed")
    win.type_ascii(pinyin, expected=target.hwnd)
    s = wait(lambda s: s["list"] and s["panel"] and s["panel"]["visible"] and s["panel"].get("content") and s.get("anchorPhys"), 5.0)
    if s is None and isinstance(target, Edge) and target.typed_raw():
        # A new browser window started in English mode: switch WeType to Chinese (Shift) in our window and retry.
        print(f"note {tag}: input method was in English mode; pressing Shift and retrying", flush=True)
        target.clear()
        win.chord("shift", expected=target.hwnd)
        time.sleep(0.3)
        win.type_ascii(pinyin, expected=target.hwnd)
        s = wait(lambda s: s["list"] and s["panel"] and s["panel"]["visible"] and s["panel"].get("content") and s.get("anchorPhys"), 5.0)
    if s is None:
        # Diagnose before retrying once: what did the app see, and what reached the text box?
        d = state()
        raw = target.typed_raw() if isinstance(target, Edge) else None
        sys.path.insert(0, str(ROOT / "backend"))
        from translate_backend import win32 as bw
        wt_visible = bool(bw.wetype_candidate_rect())
        box_len = target.text_len() if isinstance(target, Edge) else None
        print(f"note {tag}: no panel yet — list={'yes' if d['list'] else 'no'} panel_visible={bool(d['panel'] and d['panel']['visible'])} "
              f"ime={d['imeState']} wetype_window_visible={wt_visible} box_chars={box_len} plain_letters_in_box={raw} fg_is_target={win.foreground() == target.hwnd}; retrying once", flush=True)
        win.chord("esc", expected=target.hwnd)
        time.sleep(0.3)
        target.clear()
        time.sleep(0.8)
        win.type_ascii(pinyin, expected=target.hwnd)
        s = wait(lambda s: s["list"] and s["panel"] and s["panel"]["visible"] and s["panel"].get("content") and s.get("anchorPhys"), 5.0)
    if not check(f"{tag}: candidates arrive and the panel shows", s is not None):
        win.chord("esc", expected=target.hwnd)
        return False
    time.sleep(0.6)  # WeType settles its window; the bar is re-measured
    s = state()
    k = s.get("scale") or 1
    c = s["panel"]["content"]
    panel = {"x": round(c["x"] * k), "y": round(c["y"] * k), "w": round(c["w"] * k), "h": round(c["h"] * k)}
    bar = s["anchorPhys"]
    reported = s.get("caretPhys")
    truth = target.caret() or reported
    line = {"x": bar["x"], "y": truth["y"], "w": bar["w"], "h": truth["h"]} if truth else s.get("bandPhys")
    flipped = bool(truth and truth["y"] > bar["y"])
    detail = (f"bar y={bar['y']}..{bar['y'] + bar['h']} line y={line['y']}..{line['y'] + line['h']} "
              f"panel y={panel['y']}..{panel['y'] + panel['h']} dir={s.get('dir')} caret={'reported' if reported else 'not reported'}"
              f"{' (WeType flipped its bar above the caret)' if flipped else ''} measured={s.get('barMeasured')}")
    check(f"{tag}: panel clear of WeType's bar", not overlap(panel, bar), detail)
    check(f"{tag}: panel clear of the typing line", not overlap(panel, line), detail)
    check(f"{tag}: panel inside the work area", inside(panel, wa), f"panel {panel} work {wa}")
    if isinstance(target, Edge):
        check(f"{tag}: Chromium reports its caret (accessibility)", reported is not None, "reported" if reported else "not reported: the line-height fallback applies")
    win.chord("esc", expected=target.hwnd)
    wait(lambda s: s["list"] is None, 2.0)
    target.clear()
    return True


def main() -> int:
    USERDATA.mkdir(parents=True, exist_ok=True)
    (USERDATA / "config.json").write_text(json.dumps({"uiLang": "en", "autostart": False}), encoding="utf-8")
    log = USERDATA / "logs" / "translate.log"
    if log.exists():
        log.unlink()
    app = subprocess.Popen([str(EXE), f"--observe={PORT}"], env={**os.environ, "TRANSLATE_USER_DATA": str(USERDATA)})
    if not check("app starts and attaches to WeType", wait(lambda s: s["imeState"] == "connected", 15) is not None):
        app.kill()
        return 1
    wa = work_area()
    W, TK_H, EDGE_H = 560, 110, 150
    cases = [
        ("middle", lambda h: (wa["x"] + (wa["w"] - W) // 2, wa["y"] + (wa["h"] - h) // 2)),
        ("top edge", lambda h: (wa["x"] + (wa["w"] - W) // 2, wa["y"])),
        ("bottom edge", lambda h: (wa["x"] + (wa["w"] - W) // 2, wa["y"] + wa["h"] - h)),
        ("bottom-right corner", lambda h: (wa["x"] + wa["w"] - W, wa["y"] + wa["h"] - h)),
    ]
    try:
        only_edge = "--edge-only" in sys.argv
        if only_edge:
            cases = [cases[0]] * 3
        for cls, h in (((Edge, EDGE_H),) if only_edge else ((Tk, TK_H), (Edge, EDGE_H))):
            for label, pos in cases:
                x, y = pos(h)
                t = cls(x, y, W, h)
                try:
                    run_case(t, label, wa)
                finally:
                    t.close()
                    time.sleep(0.5)
            # The very bottom: the caret's line ends just above the taskbar, so WeType must draw its bar above the caret.
            hh = 64 if cls is Tk else 96
            t = cls(wa["x"] + (wa["w"] - W) // 2, wa["y"] + wa["h"] - hh, W, hh)
            try:
                run_case(t, "very bottom (bar flipped)", wa)
            finally:
                t.close()
                time.sleep(0.5)
    finally:
        try:
            urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{PORT}/quit", data=b"{}", method="POST"), timeout=2)
        except Exception:  # noqa: BLE001
            pass
        try:
            app.wait(8)
        except subprocess.TimeoutExpired:
            app.kill()
    flowing = log.exists() and "ime data flowing" in log.read_text(encoding="utf-8", errors="replace")
    check("candidate data flowed from WeType", flowing)
    out = ROOT / "measurements" / "stage6"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"live-edge-{time.strftime('%Y%m%d-%H%M%S')}.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    passed = sum(r["ok"] for r in results)
    print(json.dumps({"passed": passed, "total": len(results)}))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
