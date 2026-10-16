"""Panel placement against WeType's bar and canvas, wherever the bar is (packaged app, replay source, no input).

For bars in the middle, near each screen edge, and with "Keep the panel clickable" on: the panel never overlaps the
bar (or, when clickable, the whole IME canvas while there is room), stays inside the work area, prefers below and
flips above near the bottom. Geometry only (this PC's DPI); the DIP conversion itself is Electron's.
Run from app/:  python -X utf8 scripts/placement_test.py
"""
from __future__ import annotations

import ctypes
import json
import shutil
import sys
import time
from ctypes import wintypes as wt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "harness"))
from app import ROOT, App  # noqa: E402

USERDATA = ROOT / ".cache" / "test-userdata"
FG = {"hwnd": 1, "pid": 4242, "exe": "replay-target.exe"}
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""), flush=True)


def work_area():
    r = wt.RECT()
    ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(r), 0)  # SPI_GETWORKAREA (primary, physical)
    return {"x": r.left, "y": r.top, "w": r.right - r.left, "h": r.bottom - r.top}


def overlap(a, b):
    return a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"] and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]


def inside(a, wa):
    return a["x"] >= wa["x"] and a["y"] >= wa["y"] and a["x"] + a["w"] <= wa["x"] + wa["w"] and a["y"] + a["h"] <= wa["y"] + wa["h"]


def main() -> int:
    wa = work_area()
    if ctypes.windll.user32.GetDpiForSystem() != 96:
        print("note: system DPI is not 96; physical = DIP is assumed below")
    shutil.rmtree(USERDATA, ignore_errors=True)
    USERDATA.mkdir(parents=True)
    (USERDATA / "config.json").write_text(json.dumps({"uiLang": "en", "autostart": False}), encoding="utf-8")
    app = App(port=47471, packaged=True, extra_args=["--test-source=wetype-replay"])
    cx, cw, ch = 628, 628, 314

    def bar_at(name, cxp, cyp, bar=(27, 136, 574, 43)):
        canvas = {"x": cxp, "y": cyp, "w": cw, "h": ch}
        b = {"x": cxp + bar[0], "y": cyp + bar[1], "w": bar[2], "h": bar[3], "canvas": canvas}
        return name, b, canvas

    mid_y = wa["y"] + wa["h"] // 2 - ch // 2
    scenarios = [
        bar_at("middle", wa["x"] + 600, mid_y),
        bar_at("near the bottom", wa["x"] + 600, wa["y"] + wa["h"] - ch + 20, (27, 230, 574, 43)),
        bar_at("at the very bottom (flipped bar)", wa["x"] + 600, wa["y"] + wa["h"] - ch, (27, 262, 574, 43)),
        bar_at("near the top", wa["x"] + 600, wa["y"] - 100, (27, 104, 574, 43)),
        bar_at("right edge", wa["x"] + wa["w"] - cw + 200, mid_y),
        bar_at("left edge", wa["x"] - 20, mid_y),
        bar_at("two-line layout (2.1)", wa["x"] + 600, mid_y, (20, 109, 588, 70)),
    ]
    try:
        app.call("/wetype", {"t": "connection", "f": {"state": "connected"}})
        for clickable in (False, True):
            app.call("/settings/save", {"clickable": clickable})
            for k, (name, bar, canvas) in enumerate(scenarios):
                app.call("/wetype", {"t": "bytes", "f": {"steps": [{"k": "commit"}]}}, timeout=10)
                app.call("/wetype", {"t": "window", "f": {"rect": bar, "foreground": FG}})
                g = app.call("/wetype", {"t": "bytes", "f": {"steps": [{"k": "comp", "pinyin": "shijian" + "'" * (k % 2)}, {"k": "list", "words": ["时间", "事件", "实践", "世间", "试剑"]}]}}, timeout=10)["gen"]
                s = app.wait(lambda s: s["list"] and s["list"]["gen"] == g and s["panel"] and s["panel"]["visible"] and s["panel"].get("content"), 10)
                time.sleep(0.3)
                c = app.state()["panel"]["content"]
                tag = f"{'clickable' if clickable else 'default'} · {name}"
                room_below = bar["y"] + bar["h"] + c["h"] + 12 <= wa["y"] + wa["h"]
                if clickable:
                    room = canvas["y"] + ch + c["h"] + 12 <= wa["y"] + wa["h"] or canvas["y"] - c["h"] - 12 >= wa["y"]
                    ok = (not overlap(c, canvas)) if room else (not overlap(c, bar))
                    check(f"{tag}: clear of {'the IME window' if room else 'the bar (no room clear of the window)'}", ok, f"panel {c} bar {bar['y']}+{bar['h']}")
                else:
                    check(f"{tag}: does not cover the bar", not overlap(c, bar), f"panel {c} bar {bar['y']}+{bar['h']}")
                    below = c["y"] >= bar["y"] + bar["h"]
                    check(f"{tag}: {'below' if room_below else 'above'} the bar", below == room_below, f"panel y {c['y']}")
                check(f"{tag}: inside the work area", inside(c, wa), f"panel {c} work {wa}")
    finally:
        app.quit()
    print(json.dumps({"passed": sum(results), "total": len(results)}))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
