"""Setup checklist step 3 ("Type pinyin in any app") on the packaged app (no keyboard/mouse input, no network).

Replay candidates (sample words) translated by the built-in dictionary; no service and an in-memory key store.
Checks: not done on a fresh profile; done (and saved to progress.json) once a real translation is shown, live in an
open Settings window; unaffected by saving settings; still done after a restart.
Run from app/:  python -X utf8 scripts/setup_progress_test.py
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "harness"))
import cdp  # noqa: E402
from app import ROOT, App  # noqa: E402

USERDATA = ROOT / ".cache" / "test-userdata"
PROGRESS = USERDATA / "progress.json"
PORT = 9581
FG = {"hwnd": 1, "pid": 4242, "exe": "replay-target.exe"}
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""), flush=True)


def start() -> App:
    return App(port=47451, packaged=True, extra_args=["--test-source=wetype-replay", "--translator=live", f"--remote-debugging-port={PORT}"],
               env={"TRANSLATE_SECRETS": "memory"})


def done_count(app: App) -> int | None:
    app.call("/settings/open", {"page": "overview", "inactive": True})
    end = time.time() + 6
    while time.time() < end:
        try:
            txt = cdp.evaluate(PORT, "document.body.innerText", "settings.html")
            m = re.search(r"(\d) of 3 done", txt or "")
            if m:
                return int(m.group(1))
        except Exception:  # noqa: BLE001 — window still loading
            pass
        time.sleep(0.2)
    return None


def main() -> int:
    shutil.rmtree(USERDATA, ignore_errors=True)
    USERDATA.mkdir(parents=True)
    # No service configured: step 2 open, so the count is 1 before and 2 after step 3.
    (USERDATA / "config.json").write_text(json.dumps({"uiLang": "en", "provider": "openai", "localDict": True, "autostart": False}), encoding="utf-8")
    app = start()
    try:
        check("fresh profile: step 3 not done", done_count(app) == 1 and not PROGRESS.exists())
        app.call("/wetype", {"t": "connection", "f": {"state": "connected"}})
        app.call("/wetype", {"t": "window", "f": {"rect": {"x": 900, "y": 300, "w": 470, "h": 70}, "foreground": FG}})
        app.call("/wetype", {"t": "bytes", "f": {"steps": [{"k": "comp", "pinyin": "shijian"}, {"k": "list", "words": ["时间", "事件", "实践"]}]}}, timeout=10)
        s = app.wait(lambda s: s["list"] and "done" in s["list"]["states"], 10)
        check("a dictionary translation is shown", "dict" in (s.get("sources") or []), str(s.get("sources")))
        time.sleep(0.5)
        saved = json.loads(PROGRESS.read_text(encoding="utf-8")) if PROGRESS.exists() else None
        check("progress.json records it (a flag only)", saved == {"translatedOnce": True}, json.dumps(saved))
        txt = cdp.evaluate(PORT, "document.body.innerText", "settings.html")
        m = re.search(r"(\d) of 3 done", txt or "")
        check("open Settings window updates live", m and m.group(1) == "2", m and m.group(0))
        app.call("/settings/save", {"theme": "dark"})
        time.sleep(0.3)
        check("saving settings keeps it", PROGRESS.exists() and json.loads(PROGRESS.read_text(encoding="utf-8")) == {"translatedOnce": True})
    finally:
        app.quit()
        time.sleep(1.0)
    app = start()
    try:
        check("after a restart: still done", done_count(app) == 2)
    finally:
        app.quit()
    print(json.dumps({"passed": sum(results), "total": len(results)}))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
