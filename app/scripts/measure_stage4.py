"""Stage 4 resource measurement of the packaged app (same per-process metrics as measure.py / stage 3).

Two runs, because real typing would need keyboard input:
  live     Translate.exe in normal mode (no test control): the real WeType adapter attaches to wetype_server
           (Frida) and watches the candidate window. Idle only. Also samples wetype_server itself before,
           during and after, to show the observer's cost inside the IME process.
  replay   Translate.exe with test control and the replay source: the real adapter state machine, simulated
           translations, panel, preview and idle release, driven at 150 ms per keystroke. No Frida here, so
           its fixed cost is taken from the live run.
No input is injected. Outputs counts/timings only. Run from app/:
  python -X utf8 scripts/measure_stage4.py --label before [--phase-s 45]
"""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

import psutil

sys.argv = [a for a in sys.argv]  # measure.py reads argv at import; our flags don't collide
sys.path.insert(0, str(Path(__file__).parent / "harness"))
sys.path.insert(0, str(Path(__file__).parent))
from app import PACKAGED, ROOT, App  # noqa: E402
from measure import NCPU, Sampler, mb, summarize  # noqa: E402

args = sys.argv[1:]
LABEL = args[args.index("--label") + 1] if "--label" in args else "run"
PHASE_S = float(args[args.index("--phase-s") + 1]) if "--phase-s" in args else 45
OUT = ROOT / "measurements" / "stage4"
OUT.mkdir(parents=True, exist_ok=True)
RECT = {"x": 40, "y": 560, "w": 470, "h": 46}
FG = {"hwnd": 1, "pid": 4242, "exe": "replay-target.exe"}


def wetype_server():
    return next((p for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == "wetype_server.exe"), None)


def sample_ime(p, seconds: float) -> dict:
    if not p:
        return {}
    pts, prev, t_prev = [], p.cpu_times(), time.perf_counter()
    end = time.time() + seconds
    while time.time() < end:
        time.sleep(1)
        ct, now = p.cpu_times(), time.perf_counter()
        pts.append({"private": p.memory_info().private, "cpu": ((ct.user + ct.system) - (prev.user + prev.system)) / (now - t_prev) * 100})
        prev, t_prev = ct, now
    return {"private_mb": mb(statistics.mean(x["private"] for x in pts)), "cpu_core_pct": round(statistics.mean(x["cpu"] for x in pts), 2)}


class LiveApp:
    """Normal-mode launch (exactly what the user runs) with an isolated profile under the project."""

    def __init__(self):
        env = {**os.environ, "TRANSLATE_USER_DATA": str(ROOT / ".cache" / "live-userdata")}
        self.proc = subprocess.Popen([str(PACKAGED)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.pid = self.proc.pid

    def call(self, *a, **k):
        raise RuntimeError("no test control in live mode")

    def quit(self):
        # Closing the main process closes the backend's stdin; it detaches from the IME and exits.
        for c in psutil.Process(self.pid).children(recursive=True):
            pass
        self.proc.terminate()
        try:
            self.proc.wait(5)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(self.pid)], capture_output=True)


def live_run() -> dict:
    ime = wetype_server()
    out = {"ime_before": sample_ime(ime, 10)}
    app = LiveApp()
    smp = Sampler(app)
    smp.run_for(8)
    smp.phase = "live idle (IME attached, no window)"
    smp.run_for(PHASE_S)
    out["ime_attached"] = sample_ime(ime, 10)
    backend = next((p for p in psutil.Process(app.pid).children(recursive=True) if "python" in p.name().lower()), None)
    out["backend_threads"] = backend.num_threads() if backend else None
    out["windows_visible"] = visible_windows(app.pid)
    app.quit()
    time.sleep(3)
    out["backend_exited"] = not (backend and backend.is_running())
    out["ime_after_quit"] = sample_ime(ime, 10)
    out["phases"] = {smp.phase: summarize(smp.samples, smp.phase)}
    log = ROOT / ".cache" / "live-userdata" / "logs" / "translate.log"
    out["log_tail_ime_lines"] = [l.split(" ", 2)[-1] for l in log.read_text(encoding="utf-8").splitlines()[-200:] if " ime " in l][-3:] if log.exists() else []
    return out


def visible_windows(root_pid: int) -> int:
    import ctypes
    from ctypes import wintypes as wt
    pids = {root_pid} | {c.pid for c in psutil.Process(root_pid).children(recursive=True)}
    n = 0

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(h, _):
        nonlocal n
        pid = wt.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if pid.value in pids and ctypes.windll.user32.IsWindowVisible(h):
            n += 1
        return True

    ctypes.windll.user32.EnumWindows(cb, 0)
    return n


def replay_run() -> dict:
    app = App(port=47341, packaged=True, extra_args=["--test-source=wetype-replay", "--release-after-ms=20000"])
    smp = Sampler(app)
    wt = lambda t, **f: app.call("/wetype", {"t": t, "f": f})  # noqa: E731
    try:
        wt("connection", state="connected")
        smp.run_for(8)
        smp.phase = "1 idle (no window yet)"
        smp.run_for(PHASE_S)
        smp.phase = "2 continuous typing (adapter path, 150 ms/keystroke)"
        wt("typing", interval=150, duration=PHASE_S, rect=RECT, foreground=FG)
        smp.run_for(PHASE_S)
        smp.phase = "3 idle after typing (panel kept)"
        time.sleep(3)  # let the typing thread finish its last keystroke
        wt("window", rect=None, foreground=FG)
        smp.run_for(PHASE_S)
        smp.phase = "4 long-translation preview open"
        wt("window", rect=RECT, foreground=FG)
        wt("bytes", steps=[{"k": "comp", "pinyin": "women"}, {"k": "list", "words": ["我们明天下午三点在会议室讨论这个问题请大家提前准备好上周的数据", "我们", "我"]}])
        smp.run_for(PHASE_S)
        wt("bytes", steps=[{"k": "commit"}])
        wt("window", rect=None, foreground=FG)
        smp.phase = "5 after idle release"
        time.sleep(22)
        smp.run_for(PHASE_S)
        released = not app.state()["panelExists"]
    finally:
        app.quit()
    phases = sorted({s["phase"] for s in smp.samples if s["phase"][0].isdigit()})
    return {"released": released, "phases": {p: summarize(smp.samples, p) for p in phases}}


QUICK = "--quick" in args  # typing phase only (A/B experiments)
EXTRA = [a for a in args if a.startswith("--push-ms=")]


REAL = "--real" in args  # real pipeline + your configured service and stored key (no input injection)


def quick_run() -> dict:
    env = None
    extra = list(EXTRA)
    if REAL:
        import os, shutil
        ud = ROOT / ".cache" / "test-userdata"
        shutil.rmtree(ud, ignore_errors=True)
        ud.mkdir(parents=True)
        cfg = json.loads((Path(os.environ["APPDATA"]) / "Translate" / "config.json").read_text(encoding="utf-8"))
        (ud / "config.json").write_text(json.dumps({k: cfg[k] for k in ("provider", "services", "timeout", "target") if k in cfg}), encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if k != "TRANSLATE_SECRETS"}
        extra.append("--translator=live")
    app = App(port=47342, packaged=True, extra_args=["--test-source=wetype-replay"] + extra, env=env)
    smp = Sampler(app)
    try:
        app.call("/wetype", {"t": "connection", "f": {"state": "connected"}})
        smp.run_for(5)
        smp.phase = "typing"
        app.call("/wetype", {"t": "typing", "f": {"interval": 150, "duration": PHASE_S + 4, "rect": RECT, "foreground": FG}})
        smp.run_for(PHASE_S)
    finally:
        app.quit()
    v = summarize(smp.samples, "typing")
    return {k: v[k] for k in ("private_total", "cpu_avg_core_pct", "cpu_p95_core_pct")} | {"by_role_cpu": {r: x["cpu"] for r, x in v["by_role"].items()}}


def main():
    if QUICK:
        r = quick_run()
        (OUT / f"quick-{LABEL}.json").write_text(json.dumps(r, indent=2), encoding="utf-8")
        return print(LABEL, json.dumps(r))
    result = {"label": LABEL, "cpus": NCPU, "phase_s": PHASE_S, "time": time.strftime("%Y-%m-%d %H:%M"), "live": live_run(), "replay": replay_run()}
    (OUT / f"summary-{LABEL}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    brief = {
        "live idle": {k: result["live"]["phases"]["live idle (IME attached, no window)"].get(k) for k in ("procs", "private_total", "private_electron", "private_backend", "cpu_avg_core_pct", "cpu_backend_avg")},
        "ime": {k: result["live"][k] for k in ("ime_before", "ime_attached", "ime_after_quit", "backend_threads", "windows_visible", "backend_exited")},
        **{p: {k: v.get(k) for k in ("procs", "private_total", "private_backend", "cpu_avg_core_pct", "cpu_p95_core_pct", "cpu_backend_avg")} for p, v in result["replay"]["phases"].items()},
        "released": result["replay"]["released"],
    }
    print(json.dumps(brief, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
