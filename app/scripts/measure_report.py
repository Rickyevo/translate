"""Turns measurement output into tables (markdown) and charts (PNG).
Run from app/ after measure.py:  python -X utf8 scripts/measure_report.py
Writes measurements/stage3/report.md and measurements/stage3/*.png
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

M = Path(__file__).resolve().parents[2] / "measurements" / "stage3"
PH = ["1 idle (no window yet)", "2 continuous typing", "3 idle after typing (panel hidden)", "4 long-translation preview open", "5 settings open", "6 settings closed again"]
SHORT = ["Background idle (no window yet)", "Continuous typing", "Idle after typing (panel kept)", "Long-translation preview open", "Settings open", "Settings closed again"]


def load(v):
    p = M / f"summary-{v}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


lines: list[str] = []
d = load("default")
if d:
    lines += [f"## Default build (software rendering) — {d['cpus']} logical CPUs", "", "| Phase | Processes | Working set (MB) | Private (MB) | USS (MB) | of which backend private | CPU avg (% of one core) | CPU p95 | Backend CPU |", "|---|---|---|---|---|---|---|---|---|"]
    for k, name in zip(PH, SHORT):
        v = d["phases"][k]
        lines.append(f"| {name} | {v['procs']:.0f} | {v['ws_total']} | **{v['private_total']}** | {v['uss_total']} | {v['private_backend']} | {v['cpu_avg_core_pct']} | {v['cpu_p95_core_pct']} | {v['cpu_backend_avg']} |")
    lines += ["", "Private memory by process (MB, average over the phase):", "", "| Phase | " + " | ".join(r for r in ["main", "gpu", "utility:mojom", "renderer:panel", "renderer:settings", "renderer:preview", "backend"]) + " |", "|---" * 8 + "|"]
    for k, name in zip(PH, SHORT):
        br = d["phases"][k]["by_role"]
        lines.append(f"| {name} | " + " | ".join(str(br.get(r, {}).get("private", "—")) for r in ["main", "gpu", "utility:mojom", "renderer:panel", "renderer:settings", "renderer:preview", "backend"]) + " |")
    if "sustained_minutes" in d:
        lines += ["", f"Sustained session: {d['sustained_minutes']} min of typing bursts, previews and settings open/close cycles.", "", f"- Private at idle checkpoints: first {d['sustained_first_private_mb']} MB, last {d['sustained_last_private_mb']} MB", f"- Linear trend: total private {d['sustained_private_slope_mb_per_hour']} MB/h, working set {d['sustained_ws_slope_mb_per_hour']} MB/h, backend {d['sustained_backend_private_slope_mb_per_hour']} MB/h", f"- Checkpoints (MB): {', '.join(str(x) for x in d['sustained_checkpoints_private_mb'])}"]

lines += ["", "## Variants (same phases)", "", "| Variant | Idle, no window | Typing | Idle after typing | Preview open | Settings open | Settings closed | Typing CPU (% core) |", "|---|---|---|---|---|---|---|---|"]
for v, label in [("default", "Software rendering (default)"), ("gpu", "GPU rendering (`--gpu`)"), ("preview-separate", "Preview in its own renderer"), ("release-panel", "Release panel after 30 s idle")]:
    s = load(v)
    if not s:
        continue
    vals = [s["phases"][k].get("private_total", "—") for k in PH]
    lines.append(f"| {label} | " + " | ".join(str(x) for x in vals) + f" | {s['phases'][PH[1]].get('cpu_avg_core_pct')} |")
lines.append("")
lines.append("Values are total private MB (Electron group + backend), averaged over each phase.")
(M / "report.md").write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))

# Chart: whole run, total private + working set, with phase bands.
sp = M / "samples-default.json"
if sp.exists():
    S = json.loads(sp.read_text())
    t0 = S[0]["t"]
    xs = [(s["t"] - t0) / 60 for s in S]
    priv = [sum(r["private"] for r in s["procs"]) / 2**20 for s in S]
    ws = [sum(r["ws"] for r in s["procs"]) / 2**20 for s in S]
    be = [sum(r["private"] for r in s["procs"] if r["role"] == "backend") / 2**20 for s in S]
    cpu = [sum(r["cpu_pct"] for r in s["procs"]) for s in S]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 6.2), sharex=True, gridspec_kw={"height_ratios": [3, 2]})
    a1.plot(xs, ws, color="#9aa4b2", lw=1.2, label="Working set (incl. shared)")
    a1.plot(xs, priv, color="#1f9e81", lw=1.6, label="Private committed")
    a1.plot(xs, be, color="#c27c0e", lw=1.2, label="Backend private")
    a1.set_ylabel("MB")
    a1.set_ylim(0, max(ws) * 1.15)
    a1.legend(loc="upper left", frameon=False, fontsize=9)
    a2.plot(xs, cpu, color="#4b5563", lw=1)
    a2.set_ylabel("CPU, % of one core")
    a2.set_xlabel("minutes   (1 idle · 2 typing · 3 idle after typing · 4 preview open · 5 settings open · 6 settings closed · 7 sustained session)")
    # phase labels
    prev = None
    for x, s in zip(xs, S):
        ph = "7 sustained session" if s["phase"].startswith("7") else s["phase"]
        if ph != prev:
            for a in (a1, a2):
                a.axvline(x, color="#d1d5db", lw=0.8)
            a1.text(x + 0.08, max(ws) * 1.1, ph.split(" ", 1)[0], fontsize=8, color="#6b7280")
            prev = ph
    for a in (a1, a2):
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(M / "timeline-default.png", dpi=130)
    print("chart:", M / "timeline-default.png")
