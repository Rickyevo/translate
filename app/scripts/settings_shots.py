"""Capture every Settings page (DevTools screenshot of the window's own pixels) for review, light and dark.

Isolated profile, replay input methods (nothing attaches to a real input method); output: .cache/settings-shots/.
Run from app/:  python -X utf8 scripts/settings_shots.py [--lang en] [--dark]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "harness"))
import readme_shots  # noqa: E402  (grab: the settings window's page pixels)
from app import ROOT, App  # noqa: E402

USERDATA = ROOT / ".cache" / "test-userdata"
OUT = ROOT / ".cache" / "settings-shots"
PAGES = ["overview", "general", "translation", "appearance", "privacy", "about"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="en")
    ap.add_argument("--dark", action="store_true")
    a = ap.parse_args()
    shutil.rmtree(USERDATA, ignore_errors=True)
    USERDATA.mkdir(parents=True)
    OUT.mkdir(parents=True, exist_ok=True)
    theme = "dark" if a.dark else "light"
    (USERDATA / "config.json").write_text(json.dumps({"uiLang": a.lang, "theme": theme, "autostart": False}), encoding="utf-8")
    app = App(port=47561, extra_args=["--test-source=mspy-replay", f"--remote-debugging-port={readme_shots.CDP}"])
    try:
        app.call("/mspy", {"t": "connection", "f": {"state": "connected"}})
        app.call("/wetype", {"t": "connection", "f": {"state": "waiting"}})
        for p in PAGES:
            app.call("/settings/open", {"page": p, "inactive": True})
            time.sleep(1.6)
            img = readme_shots.grab(app, "settings")
            path = OUT / f"{p}-{a.lang}-{theme}.png"
            img.save(path)
            print(path)
            app.call("/settings/close")
            time.sleep(0.5)
    finally:
        app.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
