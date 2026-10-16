"""Microsoft Pinyin through the whole app (packaged host, replay source: synthetic UI Automation snapshots — no input
method attached, nothing typed on the desktop).

Checks: candidates show in the panel under Microsoft Pinyin's bar and clear of the typing line; a new list is a new
generation without hiding the panel; Alt+N-style insertion cancels with Esc then types; closing ends the composition;
Automatic switches from WeType to Microsoft Pinyin; Settings › General has the choice and Overview names the input
methods' independent connection states, including disconnect/reconnect transitions.
Run from app/:  python -X utf8 scripts/mspy_replay_test.py
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "harness"))
import cdp  # noqa: E402
from app import ROOT, App  # noqa: E402

USERDATA = ROOT / ".cache" / "test-userdata"
CDP = 9621
FG = {"hwnd": 1, "pid": 4242, "exe": "replay-target.exe"}
BAR = {"x": 651, "y": 419, "w": 579, "h": 36}
WIN = {"x": 641, "y": 401, "w": 599, "h": 72}
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""), flush=True)


def overlap(a, b):
    return a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"] and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]


def main() -> int:
    shutil.rmtree(USERDATA, ignore_errors=True)
    USERDATA.mkdir(parents=True)
    (USERDATA / "config.json").write_text(json.dumps({"uiLang": "en", "autostart": False}), encoding="utf-8")
    app = App(port=47541, packaged=True, extra_args=["--test-source=mspy-replay", f"--remote-debugging-port={CDP}"])
    mspy = lambda t, **f: app.call("/mspy", {"t": t, "f": f}, timeout=10)  # noqa: E731
    try:
        mspy("connection", state="connected")
        app.call("/wetype", {"t": "connection", "f": {"state": "connected"}})
        caret = {"x": 660, "y": 392, "w": 1, "h": 22}
        g1 = mspy("list", texts=["时", "是", "事", "市", "使", "式", "世"], rect=BAR, canvas=WIN, foreground={**FG, "caret": caret})["gen"]
        s = app.wait(lambda s: s["list"] and s["list"]["gen"] == g1 and s["panel"] and s["panel"]["visible"] and s["panel"].get("content"), 10)
        time.sleep(0.3)
        s = app.state()
        k = s["scale"]
        c = s["panel"]["content"]
        panel = {"x": c["x"] * k, "y": c["y"] * k, "w": c["w"] * k, "h": c["h"] * k}
        check("panel shows Microsoft Pinyin's candidates (5 of 7)", s["list"]["count"] == 5, f"count={s['list']['count']}")
        check("panel under Microsoft Pinyin's bar, left-aligned with it", panel["y"] >= BAR["y"] + BAR["h"] and abs(panel["x"] - BAR["x"]) <= 1, f"panel {panel} bar {BAR}")
        check("panel clear of the bar and the typing line", not overlap(panel, BAR) and not overlap(panel, {"x": BAR["x"], "y": caret["y"], "w": BAR["w"], "h": caret["h"]}))
        check("active input method reported", s.get("imeName") == "mspinyin", s.get("imeName"))
        hides = s["panelHides"]
        g2 = mspy("list", texts=["时间", "事件", "实践"], rect=BAR, canvas=WIN, foreground=FG)["gen"]
        s = app.wait(lambda s: s["list"] and s["list"]["gen"] == g2, 5)
        check("a keystroke's new list is a new generation; the panel stays up", s and g2 > g1 and s["panelHides"] == hides and s["panel"]["visible"])
        app.wait(lambda s: s["list"] and all(x == "done" for x in s["list"]["states"]), 5)
        app.call("/input", {"clear": True})
        r = app.call("/insert", {"gen": g2, "n": 1})
        log = app.call("/input", {})["log"]
        check("insert: Esc closes Microsoft Pinyin's window, then the translation is typed", r.get("ok") and log[:1] == [{"key": 27}] and len(log) == 2 and "text" in log[1], json.dumps({"ok": r.get("ok"), "keys": [list(x) for x in log]}))
        s = app.wait(lambda s: s["list"] is None and not s["panel"]["visible"], 3)
        check("after inserting, the composition ended and the panel hid", s is not None)
        g3 = mspy("list", texts=["你好"], rect=BAR, canvas=WIN, foreground=FG)["gen"]
        app.wait(lambda s: s["list"] and s["list"]["gen"] == g3, 5)
        mspy("close")
        s = app.wait(lambda s: s["list"] is None and not s["panel"]["visible"], 3)
        check("Microsoft Pinyin's window closing ends the composition", s is not None)
        # Automatic: WeType composing, then Microsoft Pinyin opens its window — it takes over.
        app.call("/wetype", {"t": "window", "f": {"rect": {"x": 100, "y": 200, "w": 600, "h": 46}, "foreground": FG}})
        gw = app.call("/wetype", {"t": "bytes", "f": {"steps": [{"k": "comp", "pinyin": "shi"}, {"k": "list", "words": ["时间", "事件"]}]}}, timeout=10)["gen"]
        app.wait(lambda s: s["list"] and s["list"]["gen"] == gw, 5)
        gm = mspy("list", texts=["你好", "您好"], rect=BAR, canvas=WIN, foreground=FG)["gen"]
        s = app.wait(lambda s: s["list"] and s["list"]["gen"] == gm and s.get("imeName") == "mspinyin", 5)
        check("Automatic: Microsoft Pinyin takes over from WeType (newer list shown)", s is not None and gm > gw, f"wetype gen {gw} → mspinyin gen {gm}")
        mspy("close")
        # Settings › General: the choice; Overview names the input method in use.
        app.call("/settings/open", {"page": "general", "inactive": True})
        time.sleep(1.8)
        txt = cdp.evaluate(CDP, "document.body.innerText", "settings.html") or ""
        check("Settings › General has the Input method choice", "Input method" in txt and "Automatic" in txt, "")
        app.call("/settings/close")
        time.sleep(0.6)
        app.call("/settings/open", {"page": "overview", "inactive": True})
        time.sleep(1.8)
        txt = cdp.evaluate(CDP, "document.body.innerText", "settings.html") or ""
        connection_js = "Object.fromEntries(Array.from(document.querySelectorAll('[data-ime]'), e => [e.dataset.ime,e.dataset.connected]))"
        connections = lambda: cdp.evaluate(CDP, connection_js, "settings.html")
        check("Overview shows both connected input methods", connections() == {"wetype": "true", "mspinyin": "true"})
        mspy("connection", state="failed")
        time.sleep(2.3)
        check("Microsoft Pinyin failure updates only its own row", connections() == {"wetype": "true", "mspinyin": "false"})
        mspy("connection", state="connected")
        app.call("/wetype", {"t": "connection", "f": {"state": "waiting"}})
        time.sleep(2.3)
        check("WeChat disconnect and Microsoft reconnect refresh independently", connections() == {"wetype": "false", "mspinyin": "true"})
        app.call("/settings/close")
        time.sleep(0.6)
        app.call("/settings/open", {"page": "about", "inactive": True})
        time.sleep(1.5)
        check("About shows both independent connection states", connections() == {"wetype": "false", "mspinyin": "true"})
        app.call("/settings/close")
        time.sleep(0.6)
        app.call("/settings/save", {"ime": "wetype"})
        g = mspy("list", texts=["你好"], rect=BAR, canvas=WIN, foreground=FG)["gen"]
        time.sleep(0.4)
        check("WeChat Input Method only: Microsoft Pinyin is ignored", g is None and app.state()["list"] is None, f"gen={g}")
    finally:
        app.quit()
    print(json.dumps({"passed": sum(results), "total": len(results)}))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
