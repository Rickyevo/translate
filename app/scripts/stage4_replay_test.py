"""Stage 4 end-to-end check of the real-candidate path, without the IME and without input injection.

The app runs with --test-source=wetype-replay: the backend's real WeTypeSource (framing, decoding, generations,
window/foreground tracking) is fed synthetic pipe bytes, simulated "[sim]" translations are produced as in live
mode, and insertion runs its real sequence against a recorder (DryInput) instead of SendInput. Everything the
host and panel do is real: windows, placement, lead preview, idle release, backend supervision.

Panels appear briefly near the bottom-left of the primary screen; no keyboard or mouse input is sent.
Output: per-check PASS/FAIL and a JSON summary (generations, counts, timings only; no candidate text).
Run from app/:  python -X utf8 scripts/stage4_replay_test.py [--packaged]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).parent / "harness"))
from app import ROOT, App  # noqa: E402

PACKAGED = "--packaged" in sys.argv
FG = {"hwnd": 1, "pid": 4242, "exe": "replay-target.exe"}
RECT = {"x": 60, "y": 520, "w": 470, "h": 46}
LONG = "我们明天下午三点在会议室讨论这个问题请大家提前准备好上周的数据"
results: list[tuple[str, bool, str]] = []
timings: dict[str, list[float]] = {}


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""), flush=True)


class Replay:
    def __init__(self, app: App):
        self.a = app

    def wt(self, t: str, **f):
        return self.a.call("/wetype", {"t": t, "f": f})

    def window(self, rect=RECT, fg=FG):
        return self.wt("window", rect=rect, foreground=fg)

    def keys(self, *steps, **extra):
        return self.wt("bytes", steps=list(steps), **extra)

    def compose(self, pinyin, words):
        return self.keys({"k": "comp", "pinyin": pinyin}, {"k": "list", "words": words})

    def visible(self, s):
        return bool(s["panel"] and s["panel"]["visible"])


def done(s, gen=None):
    lst = s["list"]
    return bool(lst and (gen is None or lst["gen"] == gen) and all(x == "done" for x in lst["states"]))


def run(app: App) -> None:
    r = Replay(app)
    r.wt("connection", state="connected")
    r.window()

    # 1. First list: ordering, simulated marking, panel under the IME row.
    t0 = time.perf_counter()
    g1 = r.compose("shi", ["时间", "事件", "实践", "世间", "试剑"])["gen"]
    s = app.wait(lambda s: r.visible(s) and s["list"] and s["list"]["gen"] == g1)
    timings.setdefault("show_cold_ms", []).append((time.perf_counter() - t0) * 1000)
    s = app.wait(lambda s: done(s, g1))
    check("list shown with all 5 candidates in order", s["list"]["count"] == 5 and s["list"]["gen"] == g1)
    check("translations marked simulated (footer banner + per-item source)", s["list"]["banner"] == "simulated" and all(s["list"]["sim"]), s["translationMode"])
    c = s["panel"]["content"]
    a = s["anchorDip"]
    check("panel placed directly under the candidate row", abs(c["x"] - a["x"]) <= 1 and 0 <= c["y"] - (a["y"] + a["h"]) <= 16, f"content={c} anchor={a}")

    # 2. Keystrokes inside one composition: new generations, no hide/show, same composition.
    comp, hides = s["composition"], s["panelHides"]
    gens = []
    for py, words in [("shij", ["时间", "世界"]), ("shiji", ["实际", "世纪", "时机"]), ("shijia", ["时间", "实践"])]:
        t0 = time.perf_counter()
        gens.append(r.compose(py, words)["gen"])
        app.wait(lambda s, g=gens[-1]: s["list"] and s["list"]["gen"] == g)
        timings.setdefault("show_warm_ms", []).append((time.perf_counter() - t0) * 1000)
    s = app.wait(lambda s: done(s, gens[-1]))
    check("generations strictly increase per keystroke", gens == sorted(gens) and len(set(gens)) == 3 and gens[0] > g1, str(gens))
    check("panel not hidden between keystrokes", s["panelHides"] == hides and r.visible(s))
    check("composition (width/preview state) kept across keystrokes", s["composition"] == comp)
    check("list count follows the IME (2 items)", s["list"]["count"] == 2)

    # 3. Burst of keystrokes faster than translation latency: stale results never applied.
    for i in range(6):
        last = r.compose("x" * (i + 1), ["甲", "乙", "丙", "丁"][: (i % 4) + 1])["gen"]
    s = app.wait(lambda s: done(s, last))
    ack = r.wt("window", rect=RECT, foreground=FG)
    check("burst: only the latest generation's results shown", s["list"]["gen"] == last and s["list"]["count"] == (5 % 4) + 1, f"gen={last}")
    check("burst: stale translation results dropped by the backend", ack["staleResults"] > 0, f"stale={ack['staleResults']}")

    # 4. Stale insert is refused and inserts nothing.
    app.call("/input", {"clear": True})
    res = app.call("/insert", {"gen": last - 1, "n": 1})
    log = app.call("/input", {})["log"]
    check("insert with an old generation refused as stale, nothing typed", res.get("error") == "stale" and log == [])

    # 5. Window moves (caret moves): same generation, panel follows, translations kept.
    s0 = app.state()
    r.window({**RECT, "x": RECT["x"] + 140, "y": RECT["y"] + 10})
    s = app.wait(lambda s: s["anchorDip"]["x"] != s0["anchorDip"]["x"])
    s = app.wait(lambda s: s["panel"]["content"]["x"] != s0["panel"]["content"]["x"])
    check("reposition keeps generation and translations", s["list"]["gen"] == s0["list"]["gen"] and done(s))
    check("panel follows the candidate window", abs(s["panel"]["content"]["x"] - s["anchorDip"]["x"]) <= 1, f"{s['panel']['content']['x']} vs {s['anchorDip']['x']}")

    # 6. Long candidate 1: lead preview opens automatically and tracks moves; edge-aware.
    r.window()
    gl = r.compose("women", [LONG, "我们", "我"])["gen"]
    s = app.wait(lambda s: done(s, gl) and s["preview"] is not None, timeout=6)
    pv = s["preview"]
    check("lead preview opens for a long candidate 1", pv is not None, pv and pv["kind"])
    before = pv["bounds"]
    r.window({**RECT, "x": RECT["x"] + 200})
    s = app.wait(lambda s: s["preview"] and s["preview"]["bounds"]["x"] != before["x"])
    check("lead preview tracks the candidate window", s["preview"]["bounds"]["x"] - before["x"] == 200 * 1, f"dx={s['preview']['bounds']['x'] - before['x']}")
    # Near the bottom-right corner: everything must stay inside the work area.
    import ctypes
    sw, sh = ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1)
    r.window({"x": sw - 300, "y": sh - 120, "w": 470, "h": 46})
    time.sleep(0.4)
    s = app.state()
    # Content rects (window bounds also hold the transparent shadow margin, which may overhang).
    boxes = {"panel": s["panel"]["content"]} if s["panel"] else {}
    if s["preview"]:
        boxes["preview"] = {k: s["preview"]["contentPhys"][k2] for k, k2 in (("x", "x"), ("y", "y"), ("w", "width"), ("h", "height"))}
    ok = all(b["x"] >= 0 and b["y"] >= 0 and b["x"] + b["w"] <= sw and b["y"] + b["h"] <= sh for b in boxes.values())
    above = boxes.get("panel", {}).get("y", 0) + boxes.get("panel", {}).get("h", 0) <= sh - 120
    check("edge: panel flips above and slides left; preview stays on screen", ok and above and r.visible(s), f"boxes={boxes} preview={s['preview'] and s['preview']['kind']}")
    r.window()

    # 7. Hide/show (Alt+0 path) and composition end paths.
    app.call("/toggle-hidden")
    s = app.wait(lambda s: not r.visible(s))
    check("hide panel (Alt+0 action)", not r.visible(s) and s["preview"] is None)
    app.call("/toggle-hidden")
    s = app.wait(lambda s: r.visible(s))
    check("show panel again (Alt+0 action)", r.visible(s))
    r.keys({"k": "commit"})
    s = app.wait(lambda s: s["list"] is None and not r.visible(s))
    check("commit ends the composition and hides the panel", True)
    g = r.compose("ni", ["你", "呢"])["gen"]
    app.wait(lambda s: r.visible(s) and s["list"] and s["list"]["gen"] == g)
    r.keys({"k": "comp", "pinyin": ""})
    s = app.wait(lambda s: s["list"] is None and not r.visible(s))
    check("cleared composition (Esc/backspace) hides the panel", True)
    g = r.compose("ni", ["你", "呢"])["gen"]
    app.wait(lambda s: r.visible(s))
    r.wt("window", rect=None, foreground=FG)
    s = app.wait(lambda s: s["list"] is None and not r.visible(s))
    check("candidate window hidden ends the composition", True)
    g = r.compose("ni", ["你", "呢"])["gen"]
    s = app.state()
    check("no list without a visible candidate window", s["list"] is None)
    r.window()
    g = r.compose("ni", ["你", "呢"])["gen"]
    app.wait(lambda s: r.visible(s))
    r.window(fg={**FG, "hwnd": 2})
    s = app.wait(lambda s: s["list"] is None and not r.visible(s))
    check("focus moving to another window ends the composition", True)
    r.window()

    # 8. Insertion sequence (dry): Esc first, wait for the IME to confirm, then the text.
    g = r.compose("shi", ["时间", "事件"])["gen"]
    app.wait(lambda s: done(s, g))
    app.call("/input", {"clear": True, "onEscape": "clear"})
    t0 = time.perf_counter()
    res = app.call("/insert", {"n": 1})
    timings.setdefault("insert_ms", []).append((time.perf_counter() - t0) * 1000)
    log = app.call("/input", {"clear": True})["log"]
    s = app.wait(lambda s: s["list"] is None and not r.visible(s))
    check("insert: composition cancelled (Esc) before typing", res.get("ok") and [e.get("key") for e in log[:1]] == [0x1B] and "text" in log[1], f"events={[list(e)[0] for e in log]}")
    check("insert: typed text is the marked simulated translation", log[1]["text"] == "[sim] time")
    check("insert: panel hides after insertion", not r.visible(s))
    g = r.compose("shi", ["时间", "事件"])["gen"]
    app.wait(lambda s: done(s, g))
    app.call("/input", {"onEscape": "none"})
    res = app.call("/insert", {"n": 2})
    log = app.call("/input", {"clear": True, "onEscape": "clear"})["log"]
    s = app.state()
    check("insert: IME ignores Esc → refused, nothing typed, list kept", res.get("error") == "ime" and all("text" not in e for e in log) and s["list"] and s["list"]["gen"] == g)
    app.call("/input", {"held": ["shift"]})
    res = app.call("/insert", {"n": 1})
    app.call("/input", {"held": [], "clear": True})
    check("insert: modifier still held after 1 s → refused", res.get("error") == "modifiers")
    r.keys({"k": "commit"})
    app.wait(lambda s: s["list"] is None)

    # 9. Pause: lists ignored; resume needs a fresh composition.
    app.call("/pause", {"paused": True})
    r.compose("ta", ["他", "她"])
    time.sleep(0.3)
    s = app.state()
    check("paused: no panel", s["list"] is None and not r.visible(s))
    app.call("/pause", {"paused": False})
    r.keys({"k": "list", "words": ["它"]})
    time.sleep(0.2)
    check("resume: a list without a new composition is ignored", app.state()["list"] is None)
    g = r.compose("ta", ["他"])["gen"]
    app.wait(lambda s: r.visible(s) and s["list"]["gen"] == g)
    check("resume: next composition shows", True)
    r.keys({"k": "commit"})

    # 10. IME reconnection.
    g = r.compose("hao", ["好", "号"])["gen"]
    app.wait(lambda s: r.visible(s))
    r.wt("connection", state="waiting", code="ProcessNotFoundError")
    s = app.wait(lambda s: s["list"] is None and s["imeState"] == "waiting")
    check("IME disconnect ends the composition and reports waiting", not r.visible(s))
    r.wt("connection", state="connected")
    r.keys({"k": "list", "words": ["好"]})
    time.sleep(0.2)
    check("after reconnect, a mid-composition list is ignored", app.state()["list"] is None)
    g = r.compose("hao", ["好"])["gen"]
    s = app.wait(lambda s: r.visible(s) and s["list"]["gen"] == g and s["imeState"] == "connected")
    check("after reconnect, the next composition shows", True)
    r.keys({"k": "commit"})

    # 11. Idle release and recreation of the panel renderer (release after 1.5 s in this run).
    s = app.wait(lambda s: not s["panelExists"], timeout=6)
    created = s["panelCreated"]
    check("panel renderer released after idle", not s["panelExists"])
    t0 = time.perf_counter()
    g = r.compose("zai", ["在", "再"])["gen"]
    s = app.wait(lambda s: r.visible(s) and s["list"]["gen"] == g, timeout=6)
    timings.setdefault("show_after_release_ms", []).append((time.perf_counter() - t0) * 1000)
    s = app.wait(lambda s: done(s, g))
    check("panel recreated on the next list, translations arrive", s["panelCreated"] == created + 1)
    r.keys({"k": "commit"})

    # 12. Backend crash → supervised restart; old lists are dropped, new ones work.
    g = r.compose("da", ["大", "打"])["gen"]
    app.wait(lambda s: r.visible(s))
    old = app.state()["backendPid"]
    psutil.Process(old).kill()
    s = app.wait(lambda s: s["backendPid"] != old and s["list"] is None, timeout=8)
    time.sleep(0.8)
    r.wt("connection", state="connected")
    r.window()
    g = r.compose("da", ["大"])["gen"]
    s = app.wait(lambda s: r.visible(s) and s["list"] and s["list"]["gen"] == g, timeout=5)
    check("backend restart: stale panel cleared, generations restart and display", g == 1 or s["list"]["gen"] == g)
    r.keys({"k": "commit"})


def run_clickable(app: App) -> None:
    """13. "Keep the panel clickable": clear of the IME's whole (UIAccess) window; default stays under the bar."""
    r = Replay(app)
    r.wt("connection", state="connected")
    canvas = {"x": 300, "y": 200, "w": 628, "h": 314}
    bar = {"x": 300, "y": 312, "w": 628, "h": 70, "canvas": canvas}
    r.window(bar)
    g = r.compose("shi", ["时间", "事件", "实践"])["gen"]
    s = app.wait(lambda s: r.visible(s) and done(s, g))
    c = s["panel"]["content"]
    check("default: panel directly under the bar (overlapping the IME canvas)", 0 <= c["y"] - (bar["y"] + bar["h"]) <= 16 and c["y"] < canvas["y"] + canvas["h"])
    app.call("/settings/set", {"clickable": True})
    s = app.wait(lambda s: s["panel"]["content"]["y"] >= canvas["y"] + canvas["h"])
    c = s["panel"]["content"]
    check("clickable: panel placed clear of the IME canvas", c["y"] - (canvas["y"] + canvas["h"]) <= 16, f"panel_y={c['y']} canvas_bottom={canvas['y'] + canvas['h']}")
    r.keys({"k": "commit"})
    app.wait(lambda s: s["list"] is None)
    # Long #1: the preview must not overlap the canvas either.
    r.window(bar)
    g = r.compose("women", [LONG, "我们"])["gen"]
    s = app.wait(lambda s: done(s, g) and s["preview"] is not None, timeout=6)
    pv = s["preview"]["contentPhys"]
    clear = pv["y"] >= canvas["y"] + canvas["h"] or pv["y"] + pv["height"] <= canvas["y"] or pv["x"] >= canvas["x"] + canvas["w"] or pv["x"] + pv["width"] <= canvas["x"]
    check("clickable: lead preview clear of the IME canvas", clear, f"preview={pv} kind={s['preview']['kind']}")
    r.keys({"k": "commit"})
    app.wait(lambda s: s["list"] is None)
    # Near the bottom: flips above the canvas.
    import ctypes
    sh = ctypes.windll.user32.GetSystemMetrics(1)
    low = {"x": 300, "y": sh - 360, "w": 628, "h": 314}
    r.window({"x": 300, "y": low["y"] + 112, "w": 628, "h": 70, "canvas": low})
    g = r.compose("ni", ["你", "呢"])["gen"]
    s = app.wait(lambda s: r.visible(s) and done(s, g))
    c = s["panel"]["content"]
    check("clickable near the bottom: panel above the IME canvas", c["y"] + c["h"] <= low["y"], f"panel={c} canvas_top={low['y']}")
    r.keys({"k": "commit"})
    app.call("/settings/set", {"clickable": False})


def main() -> int:
    import shutil
    shutil.rmtree(ROOT / ".cache" / "test-userdata", ignore_errors=True)  # clean settings (other suites change them)
    app = App(port=47331, packaged=PACKAGED, extra_args=["--test-source=wetype-replay", "--release-after-ms=1500"])
    try:
        run(app)
        run_clickable(app)
    except Exception as e:  # noqa: BLE001
        check("harness completed", False, f"{type(e).__name__}: {str(e)[:300]}")
    finally:
        app.quit()
    passed = sum(ok for _, ok, _ in results)
    summary = {
        "build": "packaged" if PACKAGED else "dev",
        "passed": passed,
        "total": len(results),
        "timings_ms": {k: [round(x, 1) for x in v] for k, v in timings.items()},
        "failed": [n for n, ok, _ in results if not ok],
    }
    out = ROOT / "measurements" / "stage4"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"replay-{summary['build']}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
