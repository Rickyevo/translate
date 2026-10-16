"""Settings › Overview: the "Connect a translation service" card (packaged host, no network, no keyboard/mouse input).

Shown while no service is set up; hidden with Local only, and once a key is saved. Keys go to an in-memory store for
this test (TRANSLATE_SECRETS=memory) — never to Windows Credential Manager.
Run from app/:  python -X utf8 scripts/overview_card_test.py
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
PORT = 9581
TITLE = "Connect a translation service"
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""), flush=True)


def overview_text(app: App) -> str:
    app.call("/settings/open", {"page": "overview", "inactive": True})
    end = time.time() + 6
    txt = ""
    while time.time() < end:
        try:
            txt = cdp.evaluate(PORT, "document.body.innerText", "settings.html") or ""
            if "Overview" in txt:
                break
        except Exception:  # noqa: BLE001 — still loading
            pass
        time.sleep(0.2)
    time.sleep(0.6)  # key presence arrives asynchronously
    txt = cdp.evaluate(PORT, "document.body.innerText", "settings.html") or ""
    app.call("/settings/close")
    time.sleep(0.6)
    return txt


def main() -> int:
    shutil.rmtree(USERDATA, ignore_errors=True)
    USERDATA.mkdir(parents=True)
    (USERDATA / "config.json").write_text(json.dumps({"uiLang": "en", "provider": "openai", "autostart": False}), encoding="utf-8")
    app = App(port=47451, packaged=True, extra_args=["--test-source=wetype-replay", f"--remote-debugging-port={PORT}"], env={"TRANSLATE_SECRETS": "memory"})
    try:
        t = overview_text(app)
        check("no service: the card is shown", TITLE in t)
        check("the old checklist is gone", "Finish setting up" not in t and "of 3 done" not in t)
        app.call("/settings/save", {"localOnly": True})
        check("Local only: no card", TITLE not in overview_text(app))
        app.call("/settings/save", {"localOnly": False, "apiKey": "test-key-for-overview-card"})
        check("key saved: no card", TITLE not in overview_text(app))
    finally:
        app.quit()
    print(json.dumps({"passed": sum(results), "total": len(results)}))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
