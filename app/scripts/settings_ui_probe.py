"""Settings UI probe through the DevTools protocol (DOM events only; no OS mouse/keyboard input).

Opens Settings › Translation with a custom provider pointing at the local mock service, loads a long model list,
opens the model dropdown and every other dropdown on the page, and checks for each popup:
  - it fits inside the window (no clipping), scrolls when longer than the room it has;
  - its position is stable over 1 s (no flipping between above/below = flicker).
Also checks the page scroll container (thin custom scrollbar, no arrow buttons) and that nothing overflows
horizontally. Screenshots of the open dropdown and of the scrolled page go to screenshots/stage5/.
Run from app/:  python -X utf8 scripts/settings_ui_probe.py [--packaged]
"""
from __future__ import annotations

import ctypes
import json
import shutil
import subprocess
import sys
import time
from ctypes import wintypes as wt
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).parent / "harness"))
import cdp  # noqa: E402
import win  # noqa: E402
from app import ROOT, App  # noqa: E402
from PIL import ImageGrab  # noqa: E402

PORT = 9555
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""), flush=True)


def js(expr, wait=False):
    return cdp.evaluate(PORT, expr, "settings.html", await_promise=wait)


def shot(app, name):
    h = 0
    for c in [psutil.Process(app.pid)] + psutil.Process(app.pid).children(recursive=True):
        h = win.find_window(c.pid, "Translate")
        if h:
            break
    r = wt.RECT()
    ctypes.windll.dwmapi.DwmGetWindowAttribute(wt.HWND(h), 9, ctypes.byref(r), ctypes.sizeof(r))
    ctypes.windll.user32.SetWindowPos(h, -1, 0, 0, 0, 0, 0x13)
    time.sleep(0.4)
    img = ImageGrab.grab(bbox=(r.left + 3, r.top + 3, r.right - 3, r.bottom - 4))
    (ROOT / "screenshots" / "stage5").mkdir(parents=True, exist_ok=True)
    img.save(ROOT / "screenshots" / "stage5" / f"{name}.png")


OPEN = """(async () => {
  const el = %s;
  if (!el) return 'missing';
  el.scrollIntoView({block: 'center'});
  await new Promise(r => setTimeout(r, 150));
  const o = {bubbles: true, cancelable: true, button: 0, pointerType: 'mouse', pointerId: 1, isPrimary: true};
  el.dispatchEvent(new PointerEvent('pointerdown', o)); el.dispatchEvent(new MouseEvent('mousedown', o));
  el.dispatchEvent(new PointerEvent('pointerup', o)); el.dispatchEvent(new MouseEvent('mouseup', o)); el.dispatchEvent(new MouseEvent('click', o));
  await new Promise(r => setTimeout(r, 250));
  return 'ok';
})()"""

SAMPLE = """(async () => {
  const pos = [];
  for (let i = 0; i < 60; i++) {
    const p = document.querySelector('[data-radix-popper-content-wrapper]');
    if (p) { const r = p.getBoundingClientRect(); pos.push([Math.round(r.top), Math.round(r.height)]); } else pos.push(null);
    await new Promise(r => requestAnimationFrame(r));
  }
  const p = document.querySelector('[data-radix-popper-content-wrapper]');
  const vp = p && p.querySelector('[data-radix-select-viewport]');
  const r = p && p.getBoundingClientRect();
  return {pos, inside: !!r && r.top >= 0 && r.bottom <= innerHeight + 1 && r.left >= 0 && r.right <= innerWidth + 1,
          rect: r && [Math.round(r.top), Math.round(r.bottom)], winH: innerHeight,
          scrollable: !!vp && vp.scrollHeight > vp.clientHeight + 1, canScroll: !!vp && (vp.scrollTop = 1e6, vp.scrollTop > 0),
          items: p ? p.querySelectorAll('[role=option]').length : 0};
})()"""

CLOSE = """(async () => { document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
  const p = document.querySelector('[data-radix-popper-content-wrapper]'); if (p) p.querySelector('[role=listbox], [role=menu]')?.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
  await new Promise(r => setTimeout(r, 250)); return !document.querySelector('[data-radix-popper-content-wrapper]'); })()"""


def probe_popup(name, opener, expect_scroll=False):
    r = js(OPEN % opener, True)
    if r != "ok":
        return check(f"{name}: dropdown found", False, r)
    s = js(SAMPLE, True)
    tops = {p[0] for p in s["pos"] if p}
    stable = len(tops) == 1 and all(s["pos"])
    check(f"{name}: popup stays put (no flip/flicker)", stable, f"distinct tops={sorted(tops)[:6]} frames={len(s['pos'])}")
    check(f"{name}: popup inside the window", s["inside"], f"rect={s['rect']} window_h={s['winH']} items={s['items']}")
    if expect_scroll:
        check(f"{name}: long list scrolls", s["scrollable"] and s["canScroll"])
    return s


def main() -> int:
    packaged = "--packaged" in sys.argv
    shutil.rmtree(ROOT / ".cache" / "test-userdata", ignore_errors=True)
    mock = subprocess.Popen([sys.executable, "-X", "utf8", str(ROOT / "backend" / "tests" / "mockservice.py")], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8")
    url = json.loads(mock.stdout.readline())["url"]
    mock.stdin.write(json.dumps({"models": 40}) + "\n")
    mock.stdin.flush()
    mock.stdout.readline()
    app = App(port=47395, packaged=packaged, extra_args=["--test-source=wetype-replay", "--translator=live", f"--remote-debugging-port={PORT}"], env={"TRANSLATE_SECRETS": "memory"})
    try:
        app.call("/settings/save", {"provider": "custom", "services": {"custom": {"protocol": "openai", "endpoint": url + "/v1", "model": "vendor-model-00-x", "auth": "bearer"}}, "apiKey": "k"})
        app.call("/settings/open", {"page": "translation", "inactive": True})
        time.sleep(2.5)
        # Page scroll container: thin custom scrollbar without arrow buttons; no horizontal overflow.
        sc = js("""(() => { const s = document.querySelector('.scroll-quiet'); const cs = getComputedStyle(s);
          return {thumb: getComputedStyle(s, '::-webkit-scrollbar').width, std: cs.scrollbarWidth, overflowX: s.scrollWidth > s.clientWidth + 1,
                  bodyOverflowX: document.documentElement.scrollWidth > innerWidth + 1, gutter: s.offsetWidth - s.clientWidth}; })()""")
        check("page scrollbar is the thin custom one (≤ 10 px, no classic arrows)", sc["std"] in ("auto", "") and sc["gutter"] <= 10, json.dumps(sc))
        check("no horizontal overflow on the Translation page", not sc["overflowX"] and not sc["bodyOverflowX"])
        # Load models (DOM click on the button), then the model dropdown.
        js(OPEN % "[...document.querySelectorAll('button')].find(b => /Load models/.test(b.textContent))", True)
        time.sleep(1.5)
        probe_popup("model list (40 models)", "document.querySelector('[aria-label=\"Available models\"]')", expect_scroll=True)
        shot(app, "settings-models-dropdown")
        js(CLOSE, True)
        probe_popup("service list", "document.querySelector('[aria-label=\"Service\"]')")
        js(CLOSE, True)
        probe_popup("authentication list", "document.querySelector('[aria-label=\"Authentication\"]')")
        js(CLOSE, True)
        js("document.querySelector('.scroll-quiet').scrollTop = 1e6")
        time.sleep(0.3)
        shot(app, "settings-translation-bottom")
        # Other pages with dropdowns.
        js("[...document.querySelectorAll('nav button, aside button')].find(b => /General/.test(b.textContent))?.click()")
        time.sleep(0.6)
        probe_popup("General: interface language", "document.querySelector('[aria-label=\"Interface language\"]') || [...document.querySelectorAll('button[role=combobox]')][0]")
        js(CLOSE, True)
    except Exception as e:  # noqa: BLE001
        check("probe completed", False, f"{type(e).__name__}: {str(e)[:300]}")
    finally:
        app.quit()
        mock.stdin.close()
        mock.wait(5)
    passed = sum(ok for _, ok, _ in results)
    print(json.dumps({"build": "packaged" if packaged else "dev", "passed": passed, "total": len(results)}))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
