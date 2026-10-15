"""Stage 4 LIVE acceptance: the packaged app with the real WeChat Input Method (WeType), real keystrokes and
real clicks. REQUIRES the user's explicit go-ahead: it types pinyin, presses Esc/Backspace/Space/Alt chords and
clicks the panel, but only into its own test window (Tk text box, or an Edge textarea with --edge). Every input
is guarded: if any other window comes to the foreground, the test stops without sending anything.

Privacy: candidate text and the test field's contents are compared in memory only. Output, logs and the results
file hold PASS/FAIL, generations, counts, timings and rectangles — never candidate or inserted text. The
candidate-row geometry check diffs two in-memory screen grabs of the IME window region; nothing is saved.

--clickable turns on "Keep the panel clickable"; without it the panel overlaps WeType's UIAccess window and
the click checks are expected to fail (hotkeys still pass).
Prerequisites: WeType is the active input method and in Chinese mode for new windows; don't touch the PC for
about 2 minutes. Run from app/:  python -X utf8 scripts/stage4_live_test.py [--edge]
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "harness"))
sys.path.insert(0, str(Path(__file__).parent))
import win  # noqa: E402
from app import PACKAGED, ROOT  # noqa: E402
from focus_test import EdgeTarget, TkTarget  # noqa: E402

sys.path.insert(0, str(ROOT / "backend"))
from translate_backend import win32 as bw  # noqa: E402

PORT = 47351
CLICKABLE = "--clickable" in sys.argv
# --provider=<id>: real translations from that service (key already in Credential Manager, saved by the user).
PROVIDER = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--provider=")), "")
CJK = re.compile(r"[㐀-鿿]")
USERDATA = ROOT / ".cache" / "live-test-userdata"
LOG = USERDATA / "logs" / "translate.log"
results: list[dict] = []
report_diag: dict = {}
timings: dict[str, list[float]] = {}


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append({"name": name, "ok": bool(ok), "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'}  {name}{' — ' + detail if detail else ''}", flush=True)
    return bool(ok)


def state() -> dict:
    with urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{PORT}/state", data=b"{}", method="POST"), timeout=3) as r:
        return json.loads(r.read())


def wait(pred, timeout=3.0, step=0.03):
    end = time.monotonic() + timeout
    s = state()
    while time.monotonic() < end:
        if pred(s):
            return s
        time.sleep(step)
        s = state()
    return None


def ime_rect():
    """WeType candidate window (full Flutter canvas) in physical px, or None when hidden."""
    h = bw.wetype_candidate_hwnd()
    return bw.window_rect(h) if h and bw.user32.IsWindowVisible(h) else None


def visible(s) -> bool:
    return bool(s and s["panel"] and s["panel"]["visible"])


def all_done(s) -> bool:
    """Every row settled: translated, or (with a real service) legitimately failed / no entry."""
    if PROVIDER:
        return bool(s and s["list"] and "loading" not in s["list"]["states"])
    return bool(s and s["list"] and all(x == "done" for x in s["list"]["states"]))


class Live:
    def __init__(self, t):
        self.t = t

    def keys(self, text: str, per_key_wait: float = 0.0):
        """Type ASCII as real key presses (the IME sees them). Returns generations seen after each key."""
        gens = []
        for ch in text:
            before = state()["list"]
            win.type_ascii(ch, expected=self.t.hwnd)
            if per_key_wait:
                s = wait(lambda s: s["list"] and (not before or s["list"]["gen"] != before["gen"]), per_key_wait)
                gens.append(s["list"]["gen"] if s and s["list"] else None)
        return gens

    def chord(self, *k):
        win.chord(*k, expected=self.t.hwnd)

    def clear(self):
        if isinstance(self.t, TkTarget):
            self.t.p.stdin.write("clear\n")
            self.t.p.stdin.flush()
            self.t.p.stdout.readline()
        else:
            import cdp
            cdp.evaluate(self.t.PORT, "document.getElementById('t').value=''")

    def ended(self, timeout=2.0):
        return wait(lambda s: s["list"] is None and not visible(s), timeout)

    def compose(self, pinyin: str, timeout=10.0 if PROVIDER else 3.0):
        self.keys(pinyin)
        return wait(lambda s: visible(s) and all_done(s) and s["rows"], timeout)


def text_ok(text: str, pinyin: str) -> tuple[bool, str]:
    """Inserted exactly one translation, with no pinyin left behind. Returns a text-free detail."""
    if PROVIDER:  # real English translation: non-empty, no Chinese, no pinyin
        ok = bool(text.strip()) and not CJK.search(text) and pinyin not in text and "[sim]" not in text
        return ok, f"len={len(text)} chinese_left={bool(CJK.search(text))} pinyin_left={pinyin in text}"
    ok = text.startswith("[sim] ") and text.count("[sim] ") == 1 and pinyin not in text and not re.search(r"[a-z]'[a-z]", text)
    return ok, f"len={len(text)} marked={text.startswith('[sim] ')} pinyin_left={pinyin in text}"


def row_geometry(live: Live, s) -> dict:
    """Where WeType actually draws its candidate bar, from the difference between two in-memory grabs of its
    window region (composition visible vs. hidden), excluding our own panel/preview. Numbers only."""
    from PIL import ImageChops, ImageGrab

    r = ime_rect()
    if not r:
        return {}
    box = (r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"])
    on = ImageGrab.grab(bbox=box, all_screens=True)
    ours = [x for x in (s["panel"] and s["panel"]["phys"], s["preview"] and s["preview"]["phys"]) if x]
    live.chord("esc")
    live.ended()
    time.sleep(0.25)
    off = ImageGrab.grab(bbox=box, all_screens=True)
    diff = ImageChops.difference(on.convert("RGB"), off.convert("RGB")).convert("L").point(lambda v: 255 if v > 24 else 0)
    px = diff.load()
    for o in ours:  # blank out our own windows
        for y in range(max(0, o["y"] - r["y"]), min(r["h"], o["y"] + o["height"] - r["y"])):
            for x in range(max(0, o["x"] - r["x"]), min(r["w"], o["x"] + o["width"] - r["x"])):
                px[x, y] = 0
    bb = diff.getbbox()
    del on, off, diff
    if not bb:
        return {"window": r}
    return {"window": r, "drawn": {"x": r["x"] + bb[0], "y": r["y"] + bb[1], "w": bb[2] - bb[0], "h": bb[3] - bb[1]}, "offset_top": bb[1], "drawn_h": bb[3] - bb[1]}


def run(t) -> None:
    live = Live(t)
    win.raise_window(t.hwnd)
    time.sleep(0.3)
    fx, fy = t.focus_point()
    win.click(fx, fy)
    time.sleep(0.4)
    if not check("test window has focus", t.has_focus()):
        return
    live.clear()

    # Preflight: is WeType composing in this window?
    live.keys("shi")
    s = wait(lambda s: s["list"] is not None, 3.0)
    if s is None:
        ime_up = ime_rect() is not None
        flowing = LOG.exists() and "ime data flowing" in LOG.read_text(encoding="utf-8")
        check("WeType composes in the test window (Chinese mode)", False,
              f"candidate_window_visible={ime_up} ime_data_seen={flowing}")
        if ime_up:
            live.chord("esc")
        else:
            for _ in range(3):
                live.chord("backspace")
        return
    check("WeType composes in the test window (Chinese mode)", True)
    live.chord("esc")
    live.ended()
    live.clear()

    # 1. Ordering and tracking per keystroke.
    s0 = state()
    gens = live.keys("shijian", per_key_wait=1.0)
    t_last = time.perf_counter()
    s = wait(all_done, 10 if PROVIDER else 3)
    if PROVIDER:
        timings.setdefault("last_key_to_all_translated_ms", []).append(round((time.perf_counter() - t_last) * 1000))
    ok_gens = [g for g in gens if g is not None]
    check("a new generation per keystroke, strictly increasing", len(ok_gens) == len(gens) and ok_gens == sorted(ok_gens) and len(set(ok_gens)) == len(ok_gens), f"gens={gens}")
    check("panel never hidden during the composition", s and s["panelHides"] == s0["panelHides"] and visible(s))
    check("one composition for the whole word", s and s["composition"] == s0["composition"] + 1, f"composition {s0['composition']}→{s and s['composition']}")
    r = ime_rect()
    a = s["anchorDip"] if s else None
    c = s["panel"]["content"] if s else None
    if CLICKABLE:
        cv = s["canvasDip"] if s else None
        check("panel clear of the IME window (clickable setting)", bool(cv and c and abs(c["x"] - a["x"]) <= 1 and 0 <= c["y"] - (cv["y"] + cv["h"]) <= 16), f"ime={r} panel={c}")
    else:
        check("panel directly under the IME candidate row", bool(r and c and abs(c["x"] - a["x"]) <= 1 and 0 <= c["y"] - (a["y"] + a["h"]) <= 16), f"ime={r} anchor={a} panel={c}")
    check("candidate count shown", bool(s and s["list"]["count"] >= 1), f"count={s and s['list']['count']} (compare with what WeType shows)")
    if PROVIDER:
        check("real translations arrive (dictionary + service), footer healthy",
              bool(s and s["serviceState"] == "ok" and s["list"]["banner"] is None and "ai" in s["sources"]),
              f"sources={s and s['sources']} service={s and s['serviceState']}")
        if not s:
            return

    # 2. Click insertion (row 1), focus kept, composition cancelled first.
    prev = state()["lastInsert"]
    rr = s["rows"][0]["phys"]
    cx_, cy_ = rr["x"] + rr["width"] // 2, rr["y"] + rr["height"] // 2
    win.move(cx_, cy_, expected=t.hwnd)
    time.sleep(0.4)
    import ctypes
    from ctypes import wintypes as cwt
    ctypes.windll.user32.WindowFromPoint.restype = cwt.HWND
    ctypes.windll.user32.WindowFromPoint.argtypes = [cwt.POINT]
    ctypes.windll.user32.GetAncestor.restype = cwt.HWND
    hit = ctypes.windll.user32.GetAncestor(ctypes.windll.user32.WindowFromPoint(cwt.POINT(cx_, cy_)), 2) or 0
    hit_exe = bw.process_exe(bw.window_pid(int(hit))) if hit else ""
    pre = state()
    which = "panel" if int(hit) == pre["hwnd"]["panel"] else "preview" if int(hit) == pre["hwnd"]["preview"] else hit_exe
    # z-order: is the test window (topmost Tk) above the panel? Walk down from the top.
    above, h = [], ctypes.windll.user32.GetTopWindow(None)
    while h and h != pre["hwnd"]["panel"]:
        if h == t.hwnd:
            above.append("test-window")
        h = ctypes.windll.user32.GetWindow(h, 2)
    diag = {"hit": which, "test_window_above_panel": bool(above), "preview": pre["preview"] and {"kind": pre["preview"]["kind"], "content": pre["preview"]["contentPhys"]},
            "previewWanted": pre["previewWanted"], "row1": rr, "mouse": pre["mouseLog"][-4:]}
    report_diag["before_click"] = diag
    check("the panel row is the topmost window under the pointer", which == "panel", json.dumps(diag))
    t0 = time.perf_counter()
    win.click(rr["x"] + rr["width"] // 2, rr["y"] + rr["height"] // 2, expected=t.hwnd)
    wait(lambda s: s["lastInsert"] != prev, 2.0)
    time.sleep(0.3)
    report_diag["after_click_mouse"] = state()["mouseLog"][-4:]
    timings.setdefault("click_insert_ms", []).append(round((time.perf_counter() - t0) * 1000))
    st = state()
    ok, det = text_ok(t.text(), "shijian")
    check("click: inserted the simulated translation, no pinyin left", ok and bool(st["lastInsert"] and st["lastInsert"]["ok"]), det + f" result={st['lastInsert']}")
    check("click: IME composition gone, panel hidden", ime_rect() is None and not visible(st))
    check("click: target keeps foreground and keyboard focus", t.has_focus(), win.describe(win.foreground()))
    live.clear()

    # 3. Alt+2 insertion.
    s = live.compose("shijian")
    n = min(2, s["list"]["count"]) if s else 1
    t0 = time.perf_counter()
    live.chord("alt", str(n))
    time.sleep(0.6)
    timings.setdefault("hotkey_insert_ms", []).append(round((time.perf_counter() - t0) * 1000))
    st = state()
    ok, det = text_ok(t.text(), "shijian")
    check(f"Alt+{n}: inserted, no pinyin left", ok and bool(st["lastInsert"] and st["lastInsert"]["ok"]), det + f" result={st['lastInsert']}")
    check(f"Alt+{n}: focus kept, no menu activation", t.has_focus() and ime_rect() is None, win.describe(win.foreground()))
    live.clear()

    # 4. Esc cancels: panel hides, nothing inserted. Also validates the candidate-row offsets (137/46).
    s = live.compose("nihao")
    geo = row_geometry(live, s) if s else {}
    check("Esc: composition cancelled, panel hidden, field empty", live.ended() is not None and t.text() == "")
    if geo.get("drawn"):
        check("candidate-bar offsets match where WeType draws", abs(geo["offset_top"] - 109) <= 6 and abs(geo["offset_top"] + geo["drawn_h"] - 179) <= 6, f"drawn_top={geo['offset_top']} drawn_h={geo['drawn_h']} assumed=109/70 window={geo['window']}")
    else:
        check("candidate-row geometry measured", False, "no difference found between grabs")

    # 5. Backspace to empty ends the composition.
    live.keys("ni")
    wait(visible, 2)
    live.chord("backspace")
    live.chord("backspace")
    check("Backspace to empty: panel hidden, field empty", live.ended() is not None and t.text() == "")

    # 6. Space commits the IME's own candidate: panel hides; the commit is WeType's, not ours.
    live.keys("ni")
    wait(visible, 2)
    live.chord("space")
    s = live.ended()
    txt = t.text()
    check("Space commit: panel hidden, IME committed (non-ASCII, not ours)", s is not None and len(txt) >= 1 and not txt.startswith("[sim]") and txt.isascii() is False, f"len={len(txt)}")
    live.clear()

    # 7. Long candidate 1 → lead preview, on screen, clear of the IME row; Alt+1 inserts the full text.
    s = live.compose("womenmingtianxiawusandian", timeout=10 if PROVIDER else 4)
    na = bool(s and PROVIDER and not wait(lambda s: s["previewWanted"], 1.5))  # the real #1 fits its row
    s = None if na or not s else wait(lambda s: s["preview"] is not None, 2.0)
    if na:
        check("long candidate: lead preview (N/A — the real translation fits its row)", True)
    elif check("long candidate: lead preview opens", s is not None):
        pv, r = s["preview"]["contentPhys"], ime_rect() or {}
        import ctypes
        sw, sh = ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1)
        inside = pv["x"] >= 0 and pv["y"] >= 0 and pv["x"] + pv["width"] <= sw and pv["y"] + pv["height"] <= sh
        a = s["anchorDip"]
        clear_row = pv["y"] >= a["y"] + a["h"] or pv["y"] + pv["height"] <= a["y"] or pv["x"] >= a["x"] + a["w"] or pv["x"] + pv["width"] <= a["x"]
        check("lead preview inside the screen and clear of the IME row", inside and clear_row, f"kind={s['preview']['kind']} preview={pv} row={a}")
        live.chord("alt", "1")
        time.sleep(0.6)
        ok, det = text_ok(t.text(), "women")
        check("Alt+1 inserts the long translation", ok, det)
    if not s:
        live.chord("esc")
        live.ended()
    live.clear()

    # 8. Alt+0 hide/show during a composition: the IME keeps composing; focus kept.
    live.compose("hao")
    live.chord("alt", "0")
    s = wait(lambda s: not visible(s), 1.5)
    check("Alt+0 hides the panel; IME still composing; focus kept", s is not None and ime_rect() is not None and t.has_focus())
    live.chord("alt", "0")
    s = wait(visible, 1.5)
    check("Alt+0 shows it again", s is not None and t.has_focus())
    live.chord("esc")
    live.ended()
    live.clear()

    # 9. Idle release (5 s in this run) and recreation on the next keystroke.
    s = wait(lambda s: not s["panelExists"], 8)
    created = state()["panelCreated"]
    check("panel renderer released after idle", s is not None)
    t0 = time.perf_counter()
    live.keys("hao")
    s = wait(visible, 3)
    timings.setdefault("show_after_release_ms", []).append(round((time.perf_counter() - t0) * 1000))
    check("panel recreated on the next composition", s is not None and s["panelCreated"] == created + 1)
    live.chord("esc")
    live.ended()
    live.clear()


def ordering_stats() -> dict:
    """Counts the backend logged at each composition end (no text)."""
    tot = {"compositions": 0, "lists": 0, "pinyin": 0, "dup": 0, "dropped": 0, "late": 0}
    if LOG.exists():
        for m in re.finditer(r"composition end gen=\d+ lists=(\d+) pinyin=(\d+) dup=(\d+) dropped=(\d+) late=(\d+)", LOG.read_text(encoding="utf-8")):
            tot["compositions"] += 1
            for k, v in zip(("lists", "pinyin", "dup", "dropped", "late"), m.groups()):
                tot[k] += int(v)
    return tot


def main() -> int:
    edge = "--edge" in sys.argv
    clickable = CLICKABLE  # Appearance › Keep the panel clickable (needed for mouse input)
    if LOG.exists():
        LOG.unlink()
    USERDATA.mkdir(parents=True, exist_ok=True)
    extra = {}
    if PROVIDER:  # your saved service settings (model, endpoint; config.json holds no key)
        user_cfg = json.loads((Path(os.environ["APPDATA"]) / "Translate" / "config.json").read_text(encoding="utf-8"))
        extra = {"provider": PROVIDER, "services": user_cfg.get("services") or {}, "timeout": user_cfg.get("timeout", 8)}
    (USERDATA / "config.json").write_text(json.dumps({"clickable": clickable, **extra}), encoding="utf-8")
    env = {**os.environ, "TRANSLATE_USER_DATA": str(USERDATA)}
    app = subprocess.Popen([str(PACKAGED), f"--observe={PORT}", "--release-after-ms=5000"], env=env)
    cx, cy = win.cursor()
    t = None
    try:
        s = None
        for _ in range(100):
            try:
                s = state()
                if s["imeState"] == "connected":
                    break
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.2)
        if not check("app running live and attached to WeType", bool(s and s["imeState"] == "connected"), f"ime={s and s['imeState']}"):
            return 1
        t = EdgeTarget() if edge else TkTarget()
        run(t)
    except win.ForegroundChanged as e:
        check("aborted safely: another window came to the foreground", False, str(e)[:200])
    except Exception as e:  # noqa: BLE001
        check("unexpected error", False, type(e).__name__ + ": " + str(e)[:200])
    finally:
        if t:
            t.close()
        try:
            urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{PORT}/quit", data=b"{}", method="POST"), timeout=2)
        except Exception:  # noqa: BLE001
            pass
        try:
            app.wait(5)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(app.pid)], capture_output=True)
        win.set_cursor(cx, cy)
    summary = {"diag": report_diag, "target": "edge" if edge else "tk", "clickable": clickable, "provider": PROVIDER or "sim", "passed": sum(r["ok"] for r in results), "total": len(results), "timings_ms": timings, "ordering": ordering_stats(), "results": results}
    out = ROOT / "measurements" / "stage4"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"live-{summary['target']}-{time.strftime('%Y%m%d-%H%M%S')}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("passed", "total", "timings_ms", "ordering", "diag")}, indent=1))
    return 0 if summary["passed"] == summary["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
