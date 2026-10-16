"""Memory of the packaged host, per process, with the panel and lead preview showing (replay source, no input).

Private bytes (the memory only this app uses) and working set for every process in the tree — the host, the engine,
and each WebView2 process by role (--type=…). Also times a keystroke: list sent → panel rendered (rows reported).
Optional extra WebView2 switches to compare: --wv2="<switches>" (via WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS).
Run from app/:  python -X utf8 scripts/memory_breakdown.py [Translate.exe] [--wv2="..."] [--label=name]
"""
from __future__ import annotations

import json
import os
import shutil
import statistics
import sys
import time
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).parent / "harness"))

WORDS = ["我们明天下午三点在会议室讨论这个问题并且请大家提前准备好上周的数据", "我们明天下午", "我们明天", "我们", "明天"]
# Different lengths, so every keystroke changes the panel's row layout (the render signal).
LISTS = [["你好", "您好", "拟好"], ["我们", "握们", "我门", "沃们"], ["时间", "事件", "实践", "世间", "试剑"]]  # 3, 4, 5 rows (the first list has 5)


def role(p: psutil.Process) -> str:
    try:
        cl = p.cmdline()
    except Exception:  # noqa: BLE001
        return p.name()
    t = next((a.split("=", 1)[1] for a in cl if a.startswith("--type=")), None)
    if p.name().lower() == "msedgewebview2.exe":
        if t == "utility":
            sub = next((a.split("=", 1)[1] for a in cl if a.startswith("--utility-sub-type=")), "")
            return "webview2 utility " + (sub.split(".")[0] or "?")
        return "webview2 " + (t or "browser")
    return p.name()


def snapshot(pid: int) -> list[dict]:
    out = []
    for p in [psutil.Process(pid)] + psutil.Process(pid).children(recursive=True):
        try:
            mi = p.memory_full_info()
            out.append({"role": role(p), "private_mb": round(mi.private / 2**20, 1), "ws_mb": round(mi.rss / 2**20, 1)})
        except Exception:  # noqa: BLE001
            pass
    return out


def main() -> int:
    exe = next((a for a in sys.argv[1:] if not a.startswith("--")), "")
    if exe:
        os.environ["TRANSLATE_EXE"] = exe
    extra = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--wv2=")), "")
    label = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--label=")), "default")
    import app as h
    U = h.ROOT / ".cache" / "test-userdata"
    shutil.rmtree(U, ignore_errors=True)
    U.mkdir(parents=True)
    (U / "config.json").write_text(json.dumps({"uiLang": "en", "autostart": False}), encoding="utf-8")
    # Extra switches via WebView2's own environment variable (the host's switches stay as shipped).
    env = {"WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS": extra} if extra else {}
    a = h.App(port=47494, packaged=True, extra_args=["--test-source=wetype-replay"], env=env)
    try:
        a.call("/wetype", {"t": "connection", "f": {"state": "connected"}})
        a.call("/wetype", {"t": "window", "f": {"rect": {"x": 900, "y": 300, "w": 574, "h": 43}, "foreground": {"hwnd": 1, "pid": 4242, "exe": "x.exe"}}})
        a.call("/wetype", {"t": "bytes", "f": {"steps": [{"k": "comp", "pinyin": "women"}, {"k": "list", "words": WORDS}]}}, timeout=10)
        a.wait(lambda s: s["list"] and s["panel"] and s["panel"]["visible"] and s["preview"], 20)
        # Keystroke latency: a new list → the panel's renderer has laid it out (it reports row geometry).
        lat = []
        for k in range(12):
            words = LISTS[k % 3]
            before = json.dumps(a.state()["rows"])
            t0 = time.perf_counter()
            g = a.call("/wetype", {"t": "bytes", "f": {"steps": [{"k": "comp", "pinyin": "women" + "x" * (k + 1)}, {"k": "list", "words": words}]}}, timeout=10)["gen"]
            a.wait(lambda s: s["list"] and s["list"]["gen"] == g and json.dumps(s["rows"]) != before, 5, 0.005)
            lat.append((time.perf_counter() - t0) * 1000)
        a.call("/wetype", {"t": "bytes", "f": {"steps": [{"k": "comp", "pinyin": "womenz"}, {"k": "list", "words": WORDS}]}}, timeout=10)
        time.sleep(4)  # settle: preview open, renderer idle
        snap = snapshot(a.pid)
        browser = next((p for p in [psutil.Process(a.pid)] + psutil.Process(a.pid).children(recursive=True)
                        if p.name().lower() == "msedgewebview2.exe" and not any(x.startswith("--type=") for x in p.cmdline())), None)
        switches = [x for x in (browser.cmdline() if browser else []) if x.startswith("--") and not x.startswith(("--embedded", "--webview-exe", "--user-data-dir", "--noerrdialogs", "--mojo", "--lang"))]
    finally:
        a.quit()
        time.sleep(1.5)
    total = round(sum(x["private_mb"] for x in snap), 1)
    by = {}
    for x in snap:
        by[x["role"]] = round(by.get(x["role"], 0) + x["private_mb"], 1)
    print(json.dumps({"label": label, "total_private_mb": total, "processes": len(snap), "by_role_private_mb": dict(sorted(by.items(), key=lambda kv: -kv[1])),
                      "browser_switches": switches, "keystroke_to_render_ms": {"median": round(statistics.median(lat), 1), "max": round(max(lat), 1)}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
