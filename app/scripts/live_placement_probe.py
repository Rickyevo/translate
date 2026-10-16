"""LIVE, read-only: the packaged host with the real WeChat Input Method while YOU type (no input is sent by this
script). Polls the observe endpoint (positions and counts only — never text) and checks, for every panel position
seen, that the panel does not cover WeType's bar or the typing line (when the app reports its caret) and stays inside
the monitor's work area. Isolated profile; quit your own Translate first (both would show a panel).
Run from app/:  python -X utf8 scripts/live_placement_probe.py <Translate.exe> [seconds]
"""
from __future__ import annotations

import ctypes
import json
import subprocess
import sys
import time
import urllib.request
from ctypes import wintypes as wt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "harness"))
from app import ROOT  # noqa: E402

PORT = 47511
OUT = ROOT / "measurements" / "stage6"


def state():
    with urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{PORT}/state", data=b"{}", method="POST"), timeout=2) as r:
        return json.loads(r.read())


def work_area_of(x, y):
    class MI(ctypes.Structure):
        _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]
    u = ctypes.windll.user32
    u.MonitorFromPoint.restype = wt.HANDLE
    h = u.MonitorFromPoint(wt.POINT(int(x), int(y)), 2)
    mi = MI(ctypes.sizeof(MI))
    u.GetMonitorInfoW(h, ctypes.byref(mi))
    w = mi.rcWork
    return {"x": w.left, "y": w.top, "w": w.right - w.left, "h": w.bottom - w.top}


def overlap(a, b):
    return a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"] and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]


def main() -> int:
    exe = sys.argv[1]
    seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 600
    ud = ROOT / ".cache" / "live-userdata"
    ud.mkdir(parents=True, exist_ok=True)
    (ud / "config.json").write_text(json.dumps({"uiLang": "en", "autostart": False}), encoding="utf-8")
    env = {**__import__("os").environ, "TRANSLATE_USER_DATA": str(ud)}
    p = subprocess.Popen([exe, f"--observe={PORT}"], env=env)
    seen, bad, end = {}, [], time.time() + seconds
    print(f"observing for {int(seconds)} s — type pinyin with WeChat Input Method now", flush=True)
    try:
        while time.time() < end and p.poll() is None:
            try:
                s = state()
            except Exception:  # noqa: BLE001 — starting
                time.sleep(0.2)
                continue
            pn, bar = s.get("panel"), s.get("anchorPhys")
            if pn and pn.get("visible") and bar and pn.get("content"):
                k = s.get("scale") or 1
                c = pn["content"]
                panel = {"x": round(c["x"] * k), "y": round(c["y"] * k), "w": round(c["w"] * k), "h": round(c["h"] * k)}
                caret = s.get("caretPhys")
                key = (bar["x"], bar["y"], bar["w"], bar["h"], panel["x"], panel["y"])
                if key not in seen:
                    wa = work_area_of(bar["x"] + bar["w"] / 2, bar["y"] + bar["h"] / 2)
                    line = {"x": bar["x"], "y": caret["y"], "w": bar["w"], "h": caret["h"]} if caret else None
                    v = []
                    if overlap(panel, bar):
                        v.append("covers the bar")
                    if line and overlap(panel, line):
                        v.append("covers the typing line")
                    if not (panel["x"] >= wa["x"] and panel["y"] >= wa["y"] and panel["x"] + panel["w"] <= wa["x"] + wa["w"] and panel["y"] + panel["h"] <= wa["y"] + wa["h"]):
                        v.append("outside the work area")
                    rec = {"bar": bar, "caret": caret, "panel": panel, "dir": s.get("dir"), "measured": s.get("barMeasured"), "scale": k, "work": wa,
                           "near_bottom": bar["y"] + bar["h"] > wa["y"] + wa["h"] - 300, "violations": v}
                    seen[key] = rec
                    tag = "FAIL" if v else "ok  "
                    print(f"{tag} bar y={bar['y']} h={bar['h']} caret={'yes' if caret else 'no '} dir={s.get('dir'):5} panel y={panel['y']}..{panel['y'] + panel['h']}"
                          f"{' near bottom' if rec['near_bottom'] else ''}{' — ' + ', '.join(v) if v else ''}", flush=True)
                    if v:
                        bad.append(rec)
            time.sleep(0.05)
    finally:
        try:
            urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{PORT}/quit", data=b"{}", method="POST"), timeout=2)
        except Exception:  # noqa: BLE001
            pass
        try:
            p.wait(8)
        except subprocess.TimeoutExpired:
            p.kill()
    recs = list(seen.values())
    summary = {"positions": len(recs), "with_caret": sum(1 for r in recs if r["caret"]), "near_bottom": sum(1 for r in recs if r["near_bottom"]),
               "above": sum(1 for r in recs if r["dir"] == "above"), "bar_measured": sum(1 for r in recs if r["measured"]), "violations": len(bad)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"live-placement-{time.strftime('%Y%m%d-%H%M%S')}.json").write_text(json.dumps({"summary": summary, "positions": recs}, indent=1), encoding="utf-8")
    print(json.dumps(summary))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
