"""Resource measurement of the packaged app: the whole Electron process group + the Python backend.

Method
  - Launch out/Translate-win32-x64/Translate.exe with the test-control endpoint.
  - Every second, enumerate the process tree under the main PID (renderers, GPU, utility, backend)
    and read, per process:
      working set  — physical pages mapped into the process, *including shared* pages (DLLs, shared
                     memory); summing across processes double-counts shared pages
      private      — private committed bytes (commit charge: RAM or page file), not shared
      USS          — unique set size: private pages currently resident in RAM
      CPU time     — user + kernel time; Δ over the sample interval → % of one logical core
  - Phases are driven through test control (the backend's own typing simulator generates the IME
    events, so main receives real protocol traffic, not HTTP calls).

No input is injected; settings opens without taking focus.
Run from app/:  python -X utf8 scripts/measure.py [--variant default|no-gpu|preview-separate|release-panel] [--sustained-min 20]
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).parent / "harness"))
from app import ROOT, App  # noqa: E402

args = sys.argv[1:]
VARIANT = args[args.index("--variant") + 1] if "--variant" in args else "default"
SUSTAINED_MIN = float(args[args.index("--sustained-min") + 1]) if "--sustained-min" in args else 20
PHASE_S = float(args[args.index("--phase-s") + 1]) if "--phase-s" in args else 60
OUT = ROOT / "measurements" / "stage3"
OUT.mkdir(parents=True, exist_ok=True)
FLAGS = {"default": [], "gpu": ["--gpu"], "preview-separate": ["--preview-separate"], "release-panel": ["--release-panel"]}[VARIANT]
NCPU = psutil.cpu_count()
ANCHOR = {"x": 40, "y": 560, "w": 470, "h": 52}  # bottom-left area, away from the user's work


def role(p: psutil.Process, main_pid: int, pids: dict) -> str:
    if p.pid == main_pid:
        return "main"
    try:
        name = p.name().lower()
        cmd = " ".join(p.cmdline())
    except psutil.Error:
        return "gone"
    if "python" in name:
        return "backend"
    if "--type=gpu-process" in cmd:
        return "gpu"
    if "--type=utility" in cmd:
        return "utility:" + (cmd.split("--utility-sub-type=")[1].split(" ")[0].split(".")[-2] if "--utility-sub-type=" in cmd else "?")
    if "--type=renderer" in cmd:
        for k in ("panel", "preview", "settings"):
            if pids.get(k) == p.pid:
                return f"renderer:{k}"
        return "renderer:other"
    if "--type=crashpad-handler" in cmd:
        return "crashpad"
    return "other"


class Sampler:
    def __init__(self, app: App):
        self.app = app
        self.main = psutil.Process(app.pid)
        self.prev_cpu: dict[int, float] = {}
        self.prev_t = time.perf_counter()
        self.samples: list[dict] = []
        self.phase = "start"

    def sample(self):
        try:
            pids = self.app.call("/pids", timeout=2)
        except Exception:  # noqa: BLE001
            pids = {}
        now = time.perf_counter()
        dt = now - self.prev_t
        self.prev_t = now
        procs = [self.main] + self.main.children(recursive=True)
        rows = []
        for p in procs:
            try:
                with p.oneshot():
                    mi = p.memory_info()
                    uss = p.memory_full_info().uss
                    ct = p.cpu_times()
                cpu = ct.user + ct.system
                prev = self.prev_cpu.get(p.pid)
                self.prev_cpu[p.pid] = cpu
                rows.append({"pid": p.pid, "role": role(p, self.app.pid, pids), "ws": mi.wset, "private": mi.private, "uss": uss, "cpu_pct": (cpu - prev) / dt * 100 if prev is not None else 0.0})
            except psutil.Error:
                continue
        self.samples.append({"t": time.time(), "phase": self.phase, "procs": rows})

    def run_for(self, seconds: float, every: float = 1.0):
        end = time.time() + seconds
        while time.time() < end:
            self.sample()
            time.sleep(max(0.0, every - 0.05))


def mb(b: float) -> float:
    return round(b / 2**20, 1)


def summarize(samples: list[dict], phase: str) -> dict:
    ss = [s for s in samples if s["phase"] == phase][2:]  # skip 2 s of transition
    if not ss:
        return {}

    def tot(s, key, pred=lambda r: True):
        return sum(r[key] for r in s["procs"] if pred(r))

    electron = lambda r: r["role"] != "backend"  # noqa: E731
    backend = lambda r: r["role"] == "backend"  # noqa: E731
    out = {
        "n": len(ss),
        "procs": round(statistics.mean(len(s["procs"]) for s in ss), 1),
        "ws_total": mb(statistics.mean(tot(s, "ws") for s in ss)),
        "private_total": mb(statistics.mean(tot(s, "private") for s in ss)),
        "uss_total": mb(statistics.mean(tot(s, "uss") for s in ss)),
        "private_electron": mb(statistics.mean(tot(s, "private", electron) for s in ss)),
        "private_backend": mb(statistics.mean(tot(s, "private", backend) for s in ss)),
        "ws_backend": mb(statistics.mean(tot(s, "ws", backend) for s in ss)),
        "cpu_avg_core_pct": round(statistics.mean(tot(s, "cpu_pct") for s in ss), 2),
        "cpu_p95_core_pct": round(sorted(tot(s, "cpu_pct") for s in ss)[int(0.95 * (len(ss) - 1))], 2),
        "cpu_backend_avg": round(statistics.mean(tot(s, "cpu_pct", backend) for s in ss), 2),
    }
    out["cpu_avg_machine_pct"] = round(out["cpu_avg_core_pct"] / NCPU, 3)
    roles: dict[str, list] = {}
    for s in ss:
        for r in s["procs"]:
            roles.setdefault(r["role"], []).append(r)
    out["by_role"] = {
        k: {"ws": mb(statistics.mean(r["ws"] for r in v) * len(v) / len(ss)), "private": mb(statistics.mean(r["private"] for r in v) * len(v) / len(ss)), "uss": mb(statistics.mean(r["uss"] for r in v) * len(v) / len(ss)), "cpu": round(statistics.mean(r["cpu_pct"] for r in v) * len(v) / len(ss), 2)}
        for k, v in sorted(roles.items())
    }
    return out


def main():
    app = App(packaged=True, extra_args=FLAGS)
    smp = Sampler(app)
    try:
        smp.run_for(8)  # startup settle (not reported)

        smp.phase = "1 idle (no window yet)"
        smp.run_for(PHASE_S)

        smp.phase = "2 continuous typing"
        app.call("/typing", {"interval": 150, "duration": PHASE_S, "anchor": ANCHOR, "scenarios": ["short", "short", "short"]})
        smp.run_for(PHASE_S)

        smp.phase = "3 idle after typing (panel hidden)"
        smp.run_for(PHASE_S)

        smp.phase = "4 long-translation preview open"
        app.call("/compose", {"scenario": "sentence", "anchor": ANCHOR, "latency": 80})
        time.sleep(1)
        st = app.state()
        if st.get("preview") and st.get("panel"):
            try:  # what the user actually sees (software rendering), from the real screen
                from PIL import ImageGrab

                p, pv = st["panel"]["phys"], st["preview"]["phys"]
                box = (min(p["x"], pv["x"]) - 10, min(p["y"], pv["y"]) - 10, max(p["x"] + p["width"], pv["x"] + pv["width"]) + 10, max(p["y"] + p["height"], pv["y"] + pv["height"]) + 10)
                ImageGrab.grab(bbox=box, all_screens=True).save(OUT / f"screen-preview-{VARIANT}.png")
            except Exception as e:  # noqa: BLE001
                print("screenshot failed", e)
        smp.run_for(PHASE_S)
        preview_seen = st.get("preview") is not None
        app.call("/end")

        smp.phase = "5 settings open"
        app.call("/settings/open", {"page": "overview", "inactive": True})
        smp.run_for(PHASE_S)

        smp.phase = "6 settings closed again"
        app.call("/settings/close")
        smp.run_for(PHASE_S)

        # Sustained session: repeat a realistic mix and watch idle checkpoints for growth.
        cycles = int(SUSTAINED_MIN * 60 / 60)
        for c in range(cycles):
            smp.phase = "7 sustained"
            app.call("/typing", {"interval": 150, "duration": 20, "anchor": ANCHOR, "scenarios": ["short", "short", "sentence"]})
            smp.run_for(22, every=2)
            if c % 3 == 2:
                app.call("/settings/open", {"page": ["general", "appearance", "privacy"][c % 3], "inactive": True})
                smp.run_for(8, every=2)
                app.call("/settings/close")
            smp.phase = f"7 checkpoint {c:03d}"
            smp.run_for(28 if c % 3 != 2 else 20, every=2)
    finally:
        app.quit()

    phases = ["1 idle (no window yet)", "2 continuous typing", "3 idle after typing (panel hidden)", "4 long-translation preview open", "5 settings open", "6 settings closed again"]
    summary = {"variant": VARIANT, "cpus": NCPU, "preview_seen": preview_seen, "phases": {p: summarize(smp.samples, p) for p in phases}}
    # Growth: private memory at the end of each idle checkpoint (last sample of each).
    cps = sorted({s["phase"] for s in smp.samples if s["phase"].startswith("7 checkpoint")})
    points = []
    for cp in cps:
        last = [s for s in smp.samples if s["phase"] == cp][-1]
        points.append({"t": last["t"], "private": sum(r["private"] for r in last["procs"]), "ws": sum(r["ws"] for r in last["procs"]), "backend_private": sum(r["private"] for r in last["procs"] if r["role"] == "backend")})
    if len(points) >= 3:
        t0 = points[0]["t"]
        xs = [(p["t"] - t0) / 3600 for p in points]
        for key in ("private", "ws", "backend_private"):
            ys = [p[key] / 2**20 for p in points]
            mx, my = statistics.mean(xs), statistics.mean(ys)
            slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / max(1e-9, sum((x - mx) ** 2 for x in xs))
            summary[f"sustained_{key}_slope_mb_per_hour"] = round(slope, 2)
        summary["sustained_first_private_mb"] = mb(points[0]["private"])
        summary["sustained_last_private_mb"] = mb(points[-1]["private"])
        summary["sustained_minutes"] = round((points[-1]["t"] - points[0]["t"]) / 60, 1)
        summary["sustained_checkpoints_private_mb"] = [mb(p["private"]) for p in points]
    (OUT / f"samples-{VARIANT}.json").write_text(json.dumps(smp.samples))
    (OUT / f"summary-{VARIANT}.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps(summary, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
