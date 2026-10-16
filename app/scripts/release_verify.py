"""Release verification: the packaged app, copied out of the source tree, started in an environment without any
development tools (PATH = Windows folders only; no PYTHON*/NODE*/TRANSLATE_PYTHON), in normal (live) mode.

Checks: the backend is the bundled TranslateEngine.exe; no module or DLL in the backend comes from an installed
Python, Node or the source tree; the backend reaches the IME; no visible windows; clean shutdown.
Prints counts/paths only. Run from app/:  python -X utf8 scripts/release_verify.py <release folder>
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).parent / "harness"))
from app import ROOT, clean_env  # noqa: E402

PORT = 47411
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""), flush=True)


def state():
    with urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{PORT}/state", data=b"{}", method="POST"), timeout=3) as r:
        return json.loads(r.read())


def never_drawn(h) -> bool:
    """A layered, click-through window that was never given content (no layered attributes, no bitmap) is never drawn:
    the Tauri/tao event-loop helper window ("Tao Thread Event Target", 16×16) is such a window."""
    import ctypes
    from ctypes import wintypes as wt
    u = ctypes.windll.user32
    ex = u.GetWindowLongW(h, -20) & 0xFFFFFFFF
    layered_clickthrough = ex & 0x80000 and ex & 0x20  # WS_EX_LAYERED | WS_EX_TRANSPARENT
    key, alpha, flags = wt.DWORD(), ctypes.c_byte(), wt.DWORD()
    has_attrs = u.GetLayeredWindowAttributes(h, ctypes.byref(key), ctypes.byref(alpha), ctypes.byref(flags))
    return bool(layered_clickthrough and not has_attrs)


def visible_windows(pids):
    import ctypes
    from ctypes import wintypes as wt
    n = 0

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(h, _):
        nonlocal n
        pid = wt.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if pid.value in pids and ctypes.windll.user32.IsWindowVisible(h) and not never_drawn(h):
            n += 1
        return True

    ctypes.windll.user32.EnumWindows(cb, 0)
    return n


def main() -> int:
    src = Path(sys.argv[1]).resolve()
    dest = ROOT / ".cache" / "clean-run" / "Translate"
    shutil.rmtree(dest.parent, ignore_errors=True)
    shutil.copytree(src, dest)
    exe = dest / "Translate.exe"
    ud = ROOT / ".cache" / "clean-run" / "userdata"
    env = {**clean_env(), "TRANSLATE_USER_DATA": str(ud)}
    check("environment has no Python/Node", not any(k.upper().startswith(("PYTHON", "NODE")) or k.upper() == "TRANSLATE_PYTHON" for k in env)
          and "python" not in env["PATH"].lower() and "node" not in env["PATH"].lower(), env["PATH"])
    uia_check = subprocess.run(
        [str(dest / "resources/python/TranslateEngine.exe"), "-B", "-c",
         "import sys; sys.coinit_flags=0; "
         "from translate_backend.mspinyin.observer import _load_uia; "
         "c,U=_load_uia(); a=c.client.CreateObject(U.CUIAutomation,interface=U.IUIAutomation); "
         "assert a.GetRootElement(); print('UIA_READY')"],
        env=env, capture_output=True, text=True, timeout=30,
    )
    check("Microsoft Pinyin UI Automation initializes in the bundled runtime",
          uia_check.returncode == 0 and "UIA_READY" in uia_check.stdout,
          f"exit={uia_check.returncode}")
    t0 = time.perf_counter()
    app = subprocess.Popen([str(exe), f"--observe={PORT}"], env=env, cwd=str(dest.parent))
    try:
        s = None
        for _ in range(150):
            try:
                s = state()
                if s["imeState"] == "connected":
                    break
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.1)
        ready_s = time.perf_counter() - t0
        check("app starts and the backend attaches to WeType", bool(s and s["imeState"] == "connected"), f"{ready_s:.1f} s to IME connected")
        procs = [psutil.Process(app.pid)] + psutil.Process(app.pid).children(recursive=True)
        be = next((p for p in procs if p.name().lower() == "translateengine.exe"), None)
        check("backend is the bundled runtime", be is not None and Path(be.exe()).resolve() == (dest / "resources" / "python" / "TranslateEngine.exe").resolve(),
              be.exe() if be else "no TranslateEngine.exe child")
        if be:
            files = {m.path for m in be.memory_maps()}
            bad = sorted(f for f in files if any(x in f.lower() for x in ("python312\\", "python3", "nodejs", "\\toy\\translate\\backend", "\\toy\\translate\\app\\")) and str(dest).lower() not in f.lower())
            check("backend loads nothing from an installed Python, Node or the source tree", not bad, f"{len(files)} mapped files; outside the release: {bad[:5]}")
            mods = [f for f in files if f.lower().endswith((".pyd", ".dll")) and str(dest).lower() in f.lower()]
            check("Frida, OpenSSL and ctypes load from the release folder",
                  any("_frida.pyd" in f for f in mods) and any("libssl" in f for f in mods) and any("_ctypes" in f for f in mods), f"{len(mods)} release DLL/PYD files mapped")
        check("no visible windows (no console, no main window, no tray)", visible_windows({p.pid for p in procs}) == 0)
        check("no Python or Node process outside the release", not any(p.name().lower() in ("python.exe", "pythonw.exe", "node.exe") for p in procs))
    finally:
        try:
            urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{PORT}/quit", data=b"{}", method="POST"), timeout=2)
        except Exception:  # noqa: BLE001
            pass
        try:
            app.wait(8)
            check("clean exit", True, f"code {app.returncode}")
        except subprocess.TimeoutExpired:
            app.kill()
            check("clean exit", False, "had to be killed")
    time.sleep(1)
    check("no leftover processes", not any(p.info["exe"] and str(dest).lower() in p.info["exe"].lower() for p in psutil.process_iter(["exe"])))
    passed = sum(ok for _, ok, _ in results)
    print(json.dumps({"passed": passed, "total": len(results), "copy": str(dest)}))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
