"""Visual parity of two host builds (e.g. Electron 0.1.1 vs the Tauri host): same replay input, same settings, page
pixels via DevTools (Page.captureScreenshot with a transparent background — the windows' own content, never the
desktop). Compares the panel, the lead preview and Settings pages in light and dark; writes diff images.
Run from app/:  python -X utf8 scripts/parity_shots.py <reference exe> <candidate exe>
"""
from __future__ import annotations

import base64
import io
import json
import os
import shutil
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "harness"))
import cdp  # noqa: E402
from app import ROOT  # noqa: E402
from PIL import Image, ImageChops  # noqa: E402

OUT = ROOT / ".cache" / "parity"
USERDATA = ROOT / ".cache" / "test-userdata"
PORT = 9601
FG = {"hwnd": 1, "pid": 4242, "exe": "replay-target.exe"}
RECT = {"x": 900, "y": 300, "w": 574, "h": 43}
WORDS = ["我们明天下午三点在会议室讨论这个问题并且请大家提前准备好上周的数据", "我们明天下午", "我们明天", "我们", "明天"]
PAGES = ["overview", "general", "translation", "appearance", "privacy"]


def shot(url_part: str = "", title: str = "") -> Image.Image | None:
    targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=5))
    page = next((t for t in targets if t.get("type") == "page" and url_part in t.get("url", "") and title in t.get("title", "")), None)
    if not page:
        return None
    s = cdp._ws_connect(page["webSocketDebuggerUrl"])
    try:
        msg = None
        for i, (m, p) in enumerate([("Emulation.setDefaultBackgroundColorOverride", {"color": {"r": 0, "g": 0, "b": 0, "a": 0}}), ("Page.captureScreenshot", {"format": "png"})], 1):
            cdp._send(s, json.dumps({"id": i, "method": m, "params": p}))
            while True:
                msg = json.loads(cdp._recv(s))
                if msg.get("id") == i:
                    break
        return Image.open(io.BytesIO(base64.b64decode(msg["result"]["data"]))).convert("RGBA")
    finally:
        s.close()


def run(exe: str, tag: str) -> dict[str, Image.Image]:
    os.environ["TRANSLATE_EXE"] = exe
    import importlib
    import app as harness
    importlib.reload(harness)
    shutil.rmtree(USERDATA, ignore_errors=True)
    USERDATA.mkdir(parents=True)
    (USERDATA / "config.json").write_text(json.dumps({"uiLang": "en", "autostart": False, "theme": "light"}), encoding="utf-8")
    a = harness.App(port=47491, packaged=True, extra_args=["--test-source=wetype-replay", f"--remote-debugging-port={PORT}"])
    shots = {}
    try:
        a.call("/wetype", {"t": "connection", "f": {"state": "connected"}})
        a.call("/wetype", {"t": "window", "f": {"rect": RECT, "foreground": FG}})
        for theme in ("light", "dark"):
            a.call("/settings/save", {"theme": theme})
            a.call("/wetype", {"t": "bytes", "f": {"steps": [{"k": "commit"}]}}, timeout=10)
            a.call("/wetype", {"t": "bytes", "f": {"steps": [{"k": "comp", "pinyin": "women" + theme}, {"k": "list", "words": WORDS}]}}, timeout=10)
            a.wait(lambda s: s["list"] and "loading" not in s["list"]["states"] and s["panel"] and s["panel"]["visible"], 15)
            time.sleep(1.8)  # lead preview opens (200 ms), fades finish
            shots[f"panel-{theme}"] = shot("panel.html")
            shots[f"preview-{theme}"] = shot(title="Translate preview")
            for page in PAGES:
                a.call("/settings/open", {"page": page, "inactive": True})
                time.sleep(1.6)
                shots[f"settings-{page}-{theme}"] = shot("settings.html")
                a.call("/settings/close")
                time.sleep(0.6)
    finally:
        a.quit()
        time.sleep(1.0)
    OUT.mkdir(parents=True, exist_ok=True)
    for k, im in shots.items():
        if im:
            im.save(OUT / f"{tag}-{k}.png")
    return shots


def main() -> int:
    ref, cand = sys.argv[1], sys.argv[2]
    a, b = run(ref, "ref"), run(cand, "new")
    results = {}
    worst = 0.0
    for k in a:
        x, y = a.get(k), b.get(k)
        if x is None or y is None:
            results[k] = {"missing": [k for k, v in (("ref", x), ("new", y)) if v is None]}
            continue
        if x.size != y.size:
            results[k] = {"size_ref": x.size, "size_new": y.size}
            continue
        d = ImageChops.difference(x, y)
        px = list(d.getdata())
        changed = sum(1 for q in px if max(q[:3]) > 8 and max(x.getpixel((0, 0))[3], 1))
        ratio = changed / len(px)
        worst = max(worst, ratio)
        d.convert("RGB").point(lambda v: min(255, v * 8)).save(OUT / f"diff-{k}.png")
        results[k] = {"changed_gt8": changed, "pixels": len(px), "pct": round(100 * ratio, 3), "max": max(max(q) for q in px)}
    print(json.dumps(results, indent=1))
    print(json.dumps({"worst_pct": round(100 * worst, 3), "out": str(OUT)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
