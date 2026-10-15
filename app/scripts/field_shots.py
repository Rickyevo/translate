"""Close-up captures of settings text fields (idle / focused, light / dark) for visual review. DOM focus via DevTools
(no OS input). Each crop covers the field plus a 10 px margin — no other desktop content.
Run from app/:  python -X utf8 scripts/field_shots.py [--packaged] [--tag before]
"""
from __future__ import annotations

import ctypes
import json
import shutil
import sys
import time
from ctypes import wintypes as wt
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).parent / "harness"))
import cdp  # noqa: E402
import win  # noqa: E402
from app import ROOT, App  # noqa: E402
from PIL import Image, ImageGrab  # noqa: E402

PORT = 9561
TAG = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "now"
OUT = ROOT / "screenshots" / "stage5" / "fields"


def js(e, wait=False):
    return cdp.evaluate(PORT, e, "settings.html", await_promise=wait)


def settings_hwnd(app):
    for c in [psutil.Process(app.pid)] + psutil.Process(app.pid).children(recursive=True):
        h = win.find_window(c.pid, "Translate")
        if h:
            return h
    return 0


def main():
    shutil.rmtree(ROOT / ".cache" / "test-userdata", ignore_errors=True)
    OUT.mkdir(parents=True, exist_ok=True)
    app = App(port=47412, packaged="--packaged" in sys.argv, extra_args=["--test-source=wetype-replay", f"--remote-debugging-port={PORT}"])
    tiles = []
    try:
        for theme in ("light", "dark"):
            app.call("/settings/save", {"theme": theme, "provider": "opencode-go"})
            app.call("/settings/open", {"page": "translation", "inactive": True})
            time.sleep(2.0)
            h = settings_hwnd(app)
            ctypes.windll.user32.SetWindowPos(h, -1, 0, 0, 0, 0, 0x13)
            r = wt.RECT()
            ctypes.windll.user32.GetWindowRect(h, ctypes.byref(r))
            for label, sel in (("endpoint", "#ep"), ("key", "#key"), ("model", "#model")):
                for state in ("idle", "focused"):
                    rect = js(f"""(async () => {{ const i = document.querySelector('{sel}'); i.scrollIntoView({{block: 'center'}});
                        {'i.focus();' if state == 'focused' else 'document.activeElement && document.activeElement.blur();'}
                        await new Promise(r => setTimeout(r, 300));
                        const w = i.closest('div'); const b = w.getBoundingClientRect();
                        return [b.x, b.y, b.width, b.height, devicePixelRatio]; }})()""", True)
                    x, y, w, hgt, dpr = rect
                    time.sleep(0.2)
                    box = (int(r.left + (x - 10) * dpr), int(r.top + (y - 10) * dpr), int(r.left + (x + w + 10) * dpr), int(r.top + (y + hgt + 10) * dpr))
                    img = ImageGrab.grab(bbox=box)
                    tiles.append((f"{theme} {label} {state}", img))
            app.call("/settings/close")
            time.sleep(0.8)
    finally:
        app.quit()
    # One sheet: rows = theme×field, 2× zoom so a 1 px ring/shadow is visible.
    z = 2
    wmax = max(t.width for _, t in tiles) * z
    sheet = Image.new("RGB", (wmax * 2 + 30, sum(t.height * z + 12 for _, t in tiles[::2]) + 10), (255, 0, 255))
    y = 10
    for i in range(0, len(tiles), 2):
        for j in range(2):
            t = tiles[i + j][1]
            sheet.paste(t.resize((t.width * z, t.height * z), Image.NEAREST), (10 + j * (wmax + 10), y))
        y += tiles[i][1].height * z + 12
    p = OUT / f"fields-{TAG}.png"
    sheet.save(p)
    print(json.dumps({"sheet": str(p), "tiles": [n for n, _ in tiles]}))


if __name__ == "__main__":
    main()
