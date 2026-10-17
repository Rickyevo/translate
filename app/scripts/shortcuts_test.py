"""Customizable shortcuts through the whole app (isolated profile; key presses go to the Settings page through
DevTools, never to the desktop).

Checks: recording releases Translate's global shortcuts and restores them; combinations without Alt (or Ctrl+Shift),
panel keys, Windows keys and another shortcut's keys are refused with a reason; a shortcut another app holds is
refused while recording; an accepted one goes into the draft and Save registers it (config.json, and the host runs the
right action for it); Backspace turns one off; reset restores the default; a saved shortcut another app takes shows a
warning on General and Overview, which clears by itself once the other app lets it go.
Run from app/:  python -X utf8 scripts/shortcuts_test.py
"""
from __future__ import annotations

import ctypes
import json
import shutil
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "harness"))
import cdp  # noqa: E402
from app import ROOT, App  # noqa: E402

USERDATA = ROOT / ".cache" / "test-userdata"
CDP = 9631
results = []
MOD = {"Alt": 1, "Ctrl": 2, "Shift": 8}
CODES = {"`": ("Backquote", "`"), "Backspace": ("Backspace", "Backspace"), "Escape": ("Escape", "Escape")}


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""), flush=True)


def js(expr, await_promise=False):
    return cdp.evaluate(CDP, expr, "settings.html", await_promise)


def press(accel: str):
    """Key events as the page sees a real press: modifiers down, the key, then all up."""
    parts = accel.split("+")
    *mods, key = parts
    if key in CODES:
        code, k = CODES[key]
    elif len(key) == 1 and key.isalpha():
        code, k = "Key" + key.upper(), key.lower()
    elif len(key) == 1 and key.isdigit():
        code, k = "Digit" + key, key
    else:
        code, k = key, key
    m, calls = 0, []
    for md in mods:
        m |= MOD[md]
        calls.append(("Input.dispatchKeyEvent", {"type": "rawKeyDown", "modifiers": m, "key": {"Ctrl": "Control"}.get(md, md), "code": {"Ctrl": "ControlLeft", "Alt": "AltLeft", "Shift": "ShiftLeft"}[md]}))
    calls.append(("Input.dispatchKeyEvent", {"type": "rawKeyDown", "modifiers": m, "key": k, "code": code}))
    calls.append(("Input.dispatchKeyEvent", {"type": "keyUp", "modifiers": m, "key": k, "code": code}))
    for md in reversed(mods):
        m &= ~MOD[md]
        calls.append(("Input.dispatchKeyEvent", {"type": "keyUp", "modifiers": m, "key": {"Ctrl": "Control"}.get(md, md), "code": {"Ctrl": "ControlLeft", "Alt": "AltLeft", "Shift": "ShiftLeft"}[md]}))
    cdp.call(CDP, calls, "settings.html")
    time.sleep(0.35)


def row_text(k):
    return js(f"document.querySelector('[data-shortcut={k}]')?.closest('[data-row]')?.innerText ?? null")


def click(sel):
    js(f"document.querySelector({json.dumps(sel)}).click()")
    time.sleep(0.3)


def click_text(text):
    js(f"[...document.querySelectorAll('button')].find(b => b.innerText.trim() === {json.dumps(text)}).click()")
    time.sleep(0.4)


class Holder:
    """Another app holding a global shortcut: RegisterHotKey on a thread of this process until released."""

    def __init__(self, mods: int, vk: int):
        self.ok = threading.Event()
        self.result = None
        self.tid = None
        self.t = threading.Thread(target=self._run, args=(mods, vk), daemon=True)
        self.t.start()
        self.ok.wait(3)

    def _run(self, mods, vk):
        u = ctypes.windll.user32
        self.tid = ctypes.windll.kernel32.GetCurrentThreadId()
        self.result = bool(u.RegisterHotKey(None, 0x77, mods | 0x4000, vk))
        self.ok.set()
        msg = ctypes.create_string_buffer(64)
        while u.GetMessageW(msg, None, 0, 0) > 0:
            pass
        u.UnregisterHotKey(None, 0x77)

    def release(self):
        ctypes.windll.user32.PostThreadMessageW(self.tid, 0x0012, 0, 0)  # WM_QUIT
        self.t.join(3)


def config():
    return json.loads((USERDATA / "config.json").read_text(encoding="utf-8"))


def main() -> int:
    shutil.rmtree(USERDATA, ignore_errors=True)
    USERDATA.mkdir(parents=True)
    # Shortcuts nobody else is likely to hold, so the run doesn't depend on this PC's other apps.
    base = {"pause": "Ctrl+Alt+Shift+F7", "settings": "Ctrl+Alt+Shift+F8", "toggleBar": "Alt+0"}
    (USERDATA / "config.json").write_text(json.dumps({"uiLang": "en", "autostart": False, "shortcuts": base}), encoding="utf-8")
    app = App(port=47571, extra_args=["--test-source=mspy-replay", f"--remote-debugging-port={CDP}"])
    holder = None
    try:
        app.wait(lambda s: s.get("hotkeysUnavailable") == [], 5)
        app.call("/settings/open", {"page": "general", "inactive": True})
        time.sleep(1.8)
        click("[data-shortcut=pause]")
        s = app.wait(lambda s: s.get("recordingShortcut"), 3)
        check("recording releases Translate's global shortcuts", s is not None)
        press("Ctrl+C")
        check("Ctrl+letter alone is refused (it would take a key from every app)", "Include Alt" in (row_text("pause") or ""), row_text("pause"))
        press("Alt+3")
        check("a panel key is refused", "already a panel key" in (row_text("pause") or ""))
        press("Alt+0")
        check("another shortcut's keys are refused, naming it", "Show or hide the panel" in (row_text("pause") or ""))
        press("Alt+F4")
        check("a Windows key is refused", "reserved by Windows" in (row_text("pause") or ""))
        holder = Holder(0x7, 0x7A)  # Ctrl+Alt+Shift+F11, held by "another app"
        check("(fixture) another app holds Ctrl+Alt+Shift+F11", holder.result)
        press("Ctrl+Alt+Shift+F11")
        check("a shortcut another app holds is refused while recording", "Another app is using Ctrl + Alt + Shift + F11" in (row_text("pause") or ""), row_text("pause"))
        press("Alt+Shift+K")
        txt = row_text("pause") or ""
        check("an accepted shortcut goes into the draft", "K" in txt and "Shift" in txt and "Press keys" not in txt, txt.replace("\n", " | "))
        s = app.wait(lambda s: not s.get("recordingShortcut"), 3)
        check("recording ends and Translate's shortcuts come back", s is not None)
        # Switching straight from one recorder to another keeps the shortcuts released until the last one stops.
        click("[data-shortcut=settings]")
        click("[data-shortcut=toggleBar]")
        time.sleep(0.4)
        both = js("[...document.querySelectorAll('[data-shortcut]')].filter(b => b.innerText.includes('Press keys')).map(b => b.dataset.shortcut)")
        check("one recorder at a time; shortcuts stay released when switching", both == ["toggleBar"] and app.state().get("recordingShortcut") is True, both)
        press("Escape")
        s = app.wait(lambda s: not s.get("recordingShortcut"), 3)
        check("Esc cancels without changing anything", s is not None and "Press keys" not in (row_text("toggleBar") or ""))
        check("nothing saved before Save", config()["shortcuts"]["pause"] == base["pause"])
        click_text("Save")
        time.sleep(0.6)
        check("Save writes it to config.json", config()["shortcuts"]["pause"] == "Alt+Shift+K", config()["shortcuts"])
        paused0 = app.state()["paused"]
        r = app.call("/hotkey", {"name": "Alt+Shift+K"})
        check("the new shortcut pauses", r["paused"] != paused0)
        app.call("/hotkey", {"name": "Alt+Shift+K"})
        r = app.call("/hotkey", {"name": base["pause"]})
        check("the old shortcut no longer pauses", r["paused"] == paused0)
        # Turn "Show or hide the panel" off, then reset it.
        click("[data-shortcut=toggleBar]")
        press("Backspace")
        txt = row_text("toggleBar") or ""
        check("Backspace turns a shortcut off", "Off" in txt, txt.replace("\n", " | "))
        click_text("Save")
        time.sleep(0.6)
        check("an off shortcut is saved empty", config()["shortcuts"]["toggleBar"] == "")
        hidden0 = app.state()["hidden"]
        r = app.call("/hotkey", {"name": "Alt+0"})
        check("an off shortcut does nothing", r["hidden"] == hidden0)
        js("document.querySelector('[data-shortcut=toggleBar]').closest('[data-row]').querySelector('button[aria-label=\"Reset to default\"]').click()")
        time.sleep(0.3)
        click_text("Save")
        time.sleep(0.6)
        check("reset restores the default", config()["shortcuts"]["toggleBar"] == "Alt+0")
        r = app.call("/hotkey", {"name": "Alt+0"})
        check("Alt+0 hides the panel again", r["hidden"] != hidden0)
        app.call("/hotkey", {"name": "Alt+0"})
        # A saved shortcut another app holds: warning on General and Overview; clears when it's free again.
        app.call("/settings/save", {"shortcuts": {**config()["shortcuts"], "settings": "Ctrl+Alt+Shift+F11"}})
        s = app.wait(lambda s: s.get("hotkeysUnavailable") == ["Ctrl+Alt+Shift+F11"], 5)
        check("the host reports the shortcut Windows wouldn't give it", s is not None, app.state().get("hotkeysUnavailable"))
        app.call("/settings/close")  # saved outside the window: reopen to load it
        time.sleep(0.5)
        app.call("/settings/open", {"page": "general", "inactive": True})
        time.sleep(1.6)
        check("General warns on that shortcut", "Another app is using this shortcut" in (row_text("settings") or ""))
        app.call("/settings/close")
        time.sleep(0.5)
        app.call("/settings/open", {"page": "overview", "inactive": True})
        time.sleep(1.6)
        check("Overview warns too", "Used by another app" in (js("document.body.innerText") or ""))
        holder.release()
        holder = None
        s = app.wait(lambda s: s.get("hotkeysUnavailable") == [], 6)
        check("once the other app lets go, Translate registers it (retry)", s is not None)
        time.sleep(0.4)
        check("…and the warning clears without reopening Settings", "Used by another app" not in (js("document.body.innerText") or ""))
        app.call("/settings/close")
    finally:
        if holder:
            holder.release()
        app.quit()
    print(json.dumps({"passed": sum(results), "total": len(results)}))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
