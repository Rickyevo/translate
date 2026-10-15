"""Panel ⋯ menu probe (replay source, DevTools DOM events only — no OS mouse/keyboard input).

1. Geometry: for 1–9 candidate rows, where the ⋯ button lands relative to WeType's candidate window, modelled with
   the measured live geometry (628×314 canvas; drawn bar at 109/70) — inside it, the IME's UIAccess window takes the
   click. Both placements: default (under the bar) and "Keep the panel clickable".
2. Behaviour: opens the ⋯ menu in the real panel renderer and runs its actions (Settings…, Pause/Resume, Hide panel),
   checking the effect in the app's state.
Run from app/:  python -X utf8 scripts/panel_menu_probe.py
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

PORT = 9556
FG = {"hwnd": 1, "pid": 4242, "exe": "replay-target.exe"}
CANVAS = {"x": 300, "y": 120, "w": 628, "h": 314}
BAR = {"x": 300, "y": 120 + 109, "w": 628, "h": 70, "canvas": CANVAS}
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""), flush=True)


def js(expr, wait=False):
    return cdp.evaluate(PORT, expr, "panel.html", await_promise=wait)


MORE_RECT = """(() => { const b = [...document.querySelectorAll('button')].find(x => x.getAttribute('aria-label') === 'Panel options');
  if (!b) return null; const r = b.getBoundingClientRect(); return {x: r.x + window.screenX, y: r.y + window.screenY, w: r.width, h: r.height}; })()"""

PRESS = """(async () => { const b = [...document.querySelectorAll('button')].find(x => x.getAttribute('aria-label') === 'Panel options');
  const o = {bubbles: true, cancelable: true, button: 0, pointerType: 'mouse', pointerId: 1, isPrimary: true};
  b.dispatchEvent(new PointerEvent('pointerdown', o)); b.dispatchEvent(new MouseEvent('mousedown', o));
  b.dispatchEvent(new PointerEvent('pointerup', o)); b.dispatchEvent(new MouseEvent('mouseup', o)); b.dispatchEvent(new MouseEvent('click', o));
  await new Promise(r => setTimeout(r, 300));
  return [...document.querySelectorAll('[role=menuitem]')].map(m => m.textContent.trim()); })()"""

CHOOSE = """(async () => { const m = [...document.querySelectorAll('[role=menuitem]')].find(x => x.textContent.includes(%s));
  if (!m) return 'missing'; const o = {bubbles: true, cancelable: true, button: 0, pointerType: 'mouse', pointerId: 1, isPrimary: true};
  m.dispatchEvent(new PointerEvent('pointermove', o)); m.dispatchEvent(new PointerEvent('pointerdown', o));
  m.dispatchEvent(new PointerEvent('pointerup', o)); m.dispatchEvent(new MouseEvent('click', o));
  await new Promise(r => setTimeout(r, 400)); return 'ok'; })()"""


def main() -> int:
    shutil.rmtree(ROOT / ".cache" / "test-userdata", ignore_errors=True)
    app = App(port=47403, packaged=True, extra_args=["--test-source=wetype-replay", f"--remote-debugging-port={PORT}"])
    wt = lambda t, **f: app.call("/wetype", {"t": t, "f": f})  # noqa: E731
    geo = {}
    try:
        wt("connection", state="connected")
        for clickable in (False, True):
            app.call("/settings/save", {"clickable": clickable, "count": 9})
            for rows in range(1, 10):
                wt("window", rect=BAR, foreground=FG)
                wt("bytes", steps=[{"k": "comp", "pinyin": "p" * rows}, {"k": "list", "words": [f"词{i}" for i in range(rows)]}])
                app.wait(lambda s: s["panel"] and s["panel"]["visible"] and s["list"] and s["list"]["count"] == rows and "loading" not in s["list"]["states"], 5)
                time.sleep(0.25)
                r = js(MORE_RECT)
                cx, cy = r["x"] + r["w"] / 2, r["y"] + r["h"] / 2
                covered = CANVAS["x"] <= cx < CANVAS["x"] + CANVAS["w"] and CANVAS["y"] <= cy < CANVAS["y"] + CANVAS["h"]
                geo.setdefault("clickable" if clickable else "default", {})[rows] = "covered by IME window" if covered else "reachable"
                wt("bytes", steps=[{"k": "commit"}])
        print(json.dumps(geo, indent=1))
        d = geo["default"]
        check("default placement: ⋯ covered by WeType's window for some row counts (the reported symptom)", any(v.startswith("covered") for v in d.values()),
              f"covered for rows {[k for k, v in d.items() if v.startswith('covered')]}")
        check("'Keep the panel clickable': ⋯ reachable for every row count", all(v == "reachable" for v in geo["clickable"].values()))

        # Behaviour of the menu itself.
        app.call("/settings/save", {"clickable": True, "count": 5})
        wt("window", rect=BAR, foreground=FG)
        wt("bytes", steps=[{"k": "comp", "pinyin": "ni"}, {"k": "list", "words": ["你", "呢"]}])
        app.wait(lambda s: s["panel"] and s["panel"]["visible"], 5)
        time.sleep(0.3)
        items = js(PRESS, True)
        check("⋯ opens the menu", bool(items) and len(items) >= 4, f"items={items}")
        bounds_open = app.state()["panel"]["bounds"]
        check("panel window grows to fit the open menu (not clipped)", bounds_open["height"] > 220, f"bounds={bounds_open}")
        js(CHOOSE % json.dumps("Settings"), True)
        s = app.wait(lambda s: s["settingsOpen"], 3)
        check("⋯ → Settings… opens the settings window", s is not None)
        app.call("/settings/close")
        js(PRESS, True)
        js(CHOOSE % json.dumps("Pause"), True)
        s = app.wait(lambda s: s["paused"], 3)
        check("⋯ → Pause translation pauses (and hides the panel)", s is not None and not s["panel"]["visible"])
        app.call("/pause", {"paused": False})
        wt("bytes", steps=[{"k": "comp", "pinyin": "hao"}, {"k": "list", "words": ["好", "号"]}])
        app.wait(lambda s: s["panel"] and s["panel"]["visible"], 5)
        time.sleep(0.3)
        js(PRESS, True)
        js(CHOOSE % json.dumps("Hide"), True)
        s = app.wait(lambda s: s["hidden"] and not s["panel"]["visible"], 3)
        check("⋯ → Hide panel hides it", s is not None)
        app.call("/toggle-hidden")
        wt("bytes", steps=[{"k": "commit"}])
    except Exception as e:  # noqa: BLE001
        check("probe completed", False, f"{type(e).__name__}: {str(e)[:300]}")
    finally:
        app.quit()
    passed = sum(ok for _, ok, _ in results)
    print(json.dumps({"passed": passed, "total": len(results)}))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
