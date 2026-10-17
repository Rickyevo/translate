"""Settings › Overview: the status card's service line (packaged host, no network, no keyboard/mouse input).

No service: "Dictionary only" with a "Set up a service" link; Local only says so; a saved key names the service and
model. Keys go to an in-memory store for
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
SETUP = "Set up a service"
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
            if "Translation is" in txt:
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
        check("no service: dictionary only, with a link to set one up", "Dictionary only" in t and SETUP in t)
        check("the old checklist and card are gone", "of 3 done" not in t and "Connect a translation service" not in t)
        app.call("/settings/save", {"localOnly": True})
        t = overview_text(app)
        check("Local only: says so, no setup link", "Local only" in t and SETUP not in t)
        app.call("/settings/save", {"localOnly": False, "apiKey": "test-key-for-overview-card"})
        t = overview_text(app)
        check("key saved: names the service and model", "OpenAI · gpt-6-luna" in t and SETUP not in t, t[:200])
    finally:
        app.quit()
    print(json.dumps({"passed": sum(results), "total": len(results)}))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
