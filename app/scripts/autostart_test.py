"""Start with Windows and the panel footer, on the packaged app (no keyboard/mouse input).

Start with Windows: the app adds/removes the per-user Run entry (HKCU\\...\\Run, value "Translate") for its own exe at
start and on Save. Test runs normally never touch it; TRANSLATE_LOGIN_ITEM_TEST lets this test do so. The entry is
always removed at the end (it pointed at the build under test, not at your copy).
Footer: no ⋯ menu, no language dropdown — the language pair is plain text.
Run from app/:  python -X utf8 scripts/autostart_test.py
"""
from __future__ import annotations

import json
import shutil
import sys
import time
import winreg
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "harness"))
import cdp  # noqa: E402
from app import PACKAGED, ROOT, App  # noqa: E402

RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
USERDATA = ROOT / ".cache" / "test-userdata"
PORT = 9571
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""), flush=True)


def run_value():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN) as k:
            return winreg.QueryValueEx(k, "Translate")[0]
    except FileNotFoundError:
        return None


def points_here(v):
    return bool(v) and str(PACKAGED).lower() in v.lower()


def remove_value():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, "Translate")
    except FileNotFoundError:
        pass


def main() -> int:
    before = run_value()
    if before and not points_here(before):
        print(f"a Run entry 'Translate' already exists for another copy ({before}); not touching it")
        return 2
    shutil.rmtree(USERDATA, ignore_errors=True)
    USERDATA.mkdir(parents=True)
    (USERDATA / "config.json").write_text(json.dumps({"autostart": True, "uiLang": "en"}), encoding="utf-8")
    app = App(port=47441, packaged=True, extra_args=["--test-source=wetype-replay", f"--remote-debugging-port={PORT}"], env={"TRANSLATE_LOGIN_ITEM_TEST": "1"})
    try:
        time.sleep(0.5)
        v = run_value()
        check("on at start: Run entry points at this Translate.exe", points_here(v), v or "missing")
        app.call("/settings/save", {"autostart": False})
        time.sleep(0.3)
        check("turned off and saved: Run entry removed", run_value() is None)
        app.call("/settings/save", {"autostart": True})
        time.sleep(0.3)
        check("turned on again: Run entry back", points_here(run_value()))
        app.call("/settings/save", {"autostart": False})
        time.sleep(0.3)
        check("off again: removed", run_value() is None)

        # Footer: plain-text language pair, no menu buttons.
        app.call("/wetype", {"t": "connection", "f": {"state": "connected"}})
        app.call("/wetype", {"t": "window", "f": {"rect": {"x": 900, "y": 300, "w": 470, "h": 70}, "foreground": {"hwnd": 1, "pid": 4242, "exe": "replay-target.exe"}}})
        app.call("/wetype", {"t": "bytes", "f": {"steps": [{"k": "comp", "pinyin": "shijian"}, {"k": "list", "words": ["时间", "事件", "实践"]}]}}, timeout=10)
        app.wait(lambda s: s["list"] and s["panel"] and s["panel"]["visible"], 10)
        time.sleep(0.8)
        dom = cdp.evaluate(PORT, """(() => {
            const footer = [...document.querySelectorAll('div')].find(d => typeof d.className === 'string' && d.className.includes('border-t') && d.className.includes('h-6'));
            return { footer: footer ? footer.textContent : null,
                     buttons: footer ? footer.querySelectorAll('button, [role=button], [aria-haspopup]').length : -1,
                     more: !!document.querySelector('[aria-label="Panel options"]') };
        })()""", "panel.html")
        # Replay runs show the "simulated" status in the footer; the language pair itself is checked in the README
        # captures (scripts/readme_shots.py), which use a real service.
        check("panel footer has no buttons or menus", dom["footer"] is not None and dom["buttons"] == 0, json.dumps(dom, ensure_ascii=False))
        check("no ⋯ menu button on the panel", not dom["more"])
        log = (USERDATA / "logs" / "translate.log").read_text(encoding="utf-8")
        check("version is 0.1.0", "started v0.1.0" in log)
    finally:
        app.quit()
        time.sleep(0.5)
        if points_here(run_value()):
            remove_value()
    check("no Run entry left behind", run_value() is None)
    print(json.dumps({"passed": sum(results), "total": len(results)}))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
