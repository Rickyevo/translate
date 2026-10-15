"""Row churn while typing with a real-latency service (replay source + real pipeline + local mock, 300 ms latency).

Samples the host state every ~15 ms during 20 keystrokes 150 ms apart and reports:
  skeleton_time   share of samples in which at least one row shows a grey placeholder (no text at all)
  flips           text → placeholder transitions per row position (what reads as flicker)
No input injection; synthetic candidates. Run from app/:  python -X utf8 scripts/churn_probe.py [--dev]
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "harness"))
from app import ROOT, App  # noqa: E402

FG = {"hwnd": 1, "pid": 4242, "exe": "replay-target.exe"}
RECT = {"x": 900, "y": 300, "w": 470, "h": 70}


def main() -> int:
    packaged = "--dev" not in sys.argv
    shutil.rmtree(ROOT / ".cache" / "test-userdata", ignore_errors=True)
    mock = subprocess.Popen([sys.executable, "-X", "utf8", str(ROOT / "backend" / "tests" / "mockservice.py")], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8")
    url = json.loads(mock.stdout.readline())["url"]
    mock.stdin.write(json.dumps({"delay": 0.3}) + "\n")
    mock.stdin.flush()
    mock.stdout.readline()
    app = App(port=47397, packaged=packaged, extra_args=["--test-source=wetype-replay", "--translator=live"], env={"TRANSLATE_SECRETS": "memory"})
    wt = lambda t, **f: app.call("/wetype", {"t": t, "f": f})  # noqa: E731
    try:
        app.call("/settings/save", {"provider": "custom", "services": {"custom": {"protocol": "openai", "endpoint": url + "/v1", "model": "m", "auth": "bearer"}}, "apiKey": "k"})
        wt("connection", state="connected")
        wt("window", rect=RECT, foreground=FG)
        wt("bytes", steps=[{"k": "comp", "pinyin": "a"}, {"k": "list", "words": ["甲词0", "乙词0", "丙词0", "丁词0"]}])
        app.wait(lambda s: s["list"] and "loading" not in s["list"]["states"], 5)
        samples, stop = [], threading.Event()

        def sample():
            while not stop.is_set():
                s = app.state()
                if s["list"]:
                    stale = s.get("stale") or [False] * len(s["list"]["states"])
                    samples.append([st == "loading" and not sl for st, sl in zip(s["list"]["states"], stale)])
                time.sleep(0.01)

        th = threading.Thread(target=sample)
        th.start()
        for i in range(1, 21):
            wt("bytes", steps=[{"k": "comp", "pinyin": "a" * (i + 1)}, {"k": "list", "words": [f"甲词{i}", f"乙词{i}", f"丙词{i}", f"丁词{i}"]}])
            time.sleep(0.15)
        time.sleep(1.0)
        stop.set()
        th.join()
        flips = 0
        for row in range(4):
            prev = False
            for smp in samples:
                cur = smp[row] if row < len(smp) else False
                flips += (cur and not prev)
                prev = cur
        out = {"build": "packaged" if packaged else "dev", "samples": len(samples),
               "skeleton_time": round(sum(any(x) for x in samples) / max(1, len(samples)), 3), "flips_text_to_placeholder": flips,
               "requests": None}
        mock.stdin.write("{}\n")
        mock.stdin.flush()
        out["requests"] = json.loads(mock.stdout.readline())["posts"]
        wt("bytes", steps=[{"k": "commit"}])
    finally:
        app.quit()
        mock.stdin.close()
        mock.wait(5)
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
