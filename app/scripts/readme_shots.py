"""Screenshots for the README / GitHub release: in-app captures (each window's own pixels via capturePage — never the
desktop or other apps) of the packaged app, light and dark.

Candidates come from the replay source (fixed sample sentences — never your typing); translations come from the
translation service you configured (your saved provider/model; the key stays in Windows Credential Manager and is
read only by the app). The Translation settings page is shown with the OpenAI preset and no key.
Output: screenshots/readme/*.png (+ hero-*.png composites).
Run from app/:  python -X utf8 scripts/readme_shots.py [--compose (only rebuild the composites)]
"""
from __future__ import annotations

import base64
import io
import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "harness"))
from app import ROOT, App  # noqa: E402
from PIL import Image  # noqa: E402

OUT = ROOT / "screenshots" / "readme"
USERDATA = ROOT / ".cache" / "test-userdata"
FG = {"hwnd": 1, "pid": 4242, "exe": "replay-target.exe"}
RECT = {"x": 900, "y": 300, "w": 470, "h": 70}
LISTS = {
    "en": ("women'mingtian'xiawu'sandian'zai'huiyishi'taolun", ["我们明天下午三点在会议室讨论这个问题", "我们明天下午", "我们明天", "我们", "明天"]),
    "ja": ("qing'dajia'tiqian'zhunbei'hao", ["请大家提前准备好上周的数据", "请大家提前准备", "请大家", "提前", "准备"]),
}


def grab(app: App, win: str) -> Image.Image:
    r = app.call("/capture", {"win": win}, timeout=10)
    if not r or not r.get("ok"):
        raise RuntimeError(f"no {win} window to capture")
    img = Image.open(io.BytesIO(base64.b64decode(r["png"]))).convert("RGBA")
    box = img.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    return img.crop(box) if box else img


def show(app: App, k: int, pinyin: str, words: list[str]):
    app.call("/wetype", {"t": "bytes", "f": {"steps": [{"k": "commit"}]}}, timeout=10)
    g = app.call("/wetype", {"t": "bytes", "f": {"steps": [{"k": "comp", "pinyin": pinyin + "'" * (k % 2)}, {"k": "list", "words": words}]}}, timeout=10)["gen"]
    app.wait(lambda s: s["list"] and s["list"]["gen"] == g and "loading" not in s["list"]["states"], 30, 0.05)
    time.sleep(3.0)  # dictionary glosses refined by the service, lead preview open, fades finished


def compose():
    """README hero images: the panel and the lead preview side by side on GitHub's page colour for each theme."""
    for theme, bg in (("light", (255, 255, 255, 255)), ("dark", (13, 17, 23, 255))):
        for target in ("en", "ja"):
            panel, preview = (Image.open(OUT / f"{w}-{target}-{theme}.png") for w in ("panel", "preview"))
            pad, gap = 24, 20
            img = Image.new("RGBA", (pad * 2 + panel.width + gap + preview.width, pad * 2 + max(panel.height, preview.height)), bg)
            img.alpha_composite(panel, (pad, pad))
            img.alpha_composite(preview, (pad + panel.width + gap, pad))
            img.convert("RGB").save(OUT / f"hero-{target}-{theme}.png")


def main() -> int:
    if "--compose" in sys.argv:
        return compose() or 0
    user_cfg = json.loads((Path(os.environ["APPDATA"]) / "Translate" / "config.json").read_text(encoding="utf-8"))
    shutil.rmtree(USERDATA, ignore_errors=True)
    USERDATA.mkdir(parents=True)
    base = {"provider": user_cfg.get("provider", "openai"), "services": user_cfg.get("services") or {}, "timeout": 20,
            "target": "en", "localDict": True, "localOnly": False, "uiLang": "en", "theme": "light", "autostart": False}
    (USERDATA / "config.json").write_text(json.dumps(base), encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k != "TRANSLATE_SECRETS"}  # the real vault: your stored key
    app = App(port=47431, packaged=True, extra_args=["--test-source=wetype-replay", "--translator=live"], env=env)
    saved = []
    try:
        app.call("/wetype", {"t": "connection", "f": {"state": "connected"}})
        app.call("/wetype", {"t": "window", "f": {"rect": RECT, "foreground": FG}})
        k = 0
        for theme in ("light", "dark"):
            for target in ("en", "ja"):
                app.call("/settings/save", {"theme": theme, "target": target})
                time.sleep(0.6)
                k += 1
                show(app, k, *LISTS[target])
                for win in ("panel", "preview"):
                    p = OUT / f"{win}-{target}-{theme}.png"
                    grab(app, win).save(p)
                    saved.append(p.name)
            # Settings: overview with the configured (working) service; then Translation with the OpenAI preset, no key.
            app.call("/wetype", {"t": "bytes", "f": {"steps": [{"k": "commit"}]}}, timeout=10)
            app.call("/settings/save", {"target": "en"})
            for page in ("overview", "appearance"):
                app.call("/settings/open", {"page": page, "inactive": True})
                time.sleep(1.5)
                p = OUT / f"settings-{page}-{theme}.png"
                grab(app, "settings").save(p)
                saved.append(p.name)
                app.call("/settings/close")
                time.sleep(0.6)
        app.call("/settings/save", {"theme": "light", "provider": "openai"})
        app.call("/settings/open", {"page": "translation", "inactive": True})
        time.sleep(1.5)
        p = OUT / "settings-translation-light.png"
        grab(app, "settings").save(p)
        saved.append(p.name)
        app.call("/settings/close")
    finally:
        app.quit()
    compose()
    print(json.dumps({"out": str(OUT), "files": saved}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
