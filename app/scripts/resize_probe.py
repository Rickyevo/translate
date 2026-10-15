"""Counts panel/preview window resizes during one composition of realistic typing (replay source, real pipeline,
local mock with 300 ms latency): rows appearing/disappearing and translations of different lengths. Each resize can
show one stale or blank frame. No input injection. Run from app/:  python -X utf8 scripts/resize_probe.py [--dev]"""
import json, shutil, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "harness"))
from app import ROOT, App
FG = {"hwnd": 1, "pid": 4242, "exe": "replay-target.exe"}
RECT = {"x": 900, "y": 300, "w": 470, "h": 70}
shutil.rmtree(ROOT / ".cache" / "test-userdata", ignore_errors=True)
mock = subprocess.Popen([sys.executable, "-X", "utf8", str(ROOT / "backend" / "tests" / "mockservice.py")], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8")
url = json.loads(mock.stdout.readline())["url"]
mock.stdin.write(json.dumps({"delay": 0.3}) + "\n"); mock.stdin.flush(); mock.stdout.readline()
app = App(port=47414, packaged="--dev" not in sys.argv, extra_args=["--test-source=wetype-replay", "--translator=live"], env={"TRANSLATE_SECRETS": "memory"})
wt = lambda t, **f: app.call("/wetype", {"t": t, "f": f})
try:
    app.call("/settings/save", {"provider": "custom", "services": {"custom": {"protocol": "openai", "endpoint": url + "/v1", "model": "m", "auth": "bearer"}}, "apiKey": "k"})
    wt("connection", state="connected"); wt("window", rect=RECT, foreground=FG)
    seq = ["我", "我们", "我们明", "我们明天", "我们明天下", "我们明天下午", "我们明天下午三", "我们明天下午三点开会讨论", "我们明天下午三点开会讨论这个问题"]
    wt("bytes", steps=[{"k": "comp", "pinyin": "w"}, {"k": "list", "words": ["我"]}])
    app.wait(lambda s: s["panel"] and s["panel"]["visible"], 5); time.sleep(0.8)
    r0 = app.state()["windowResizes"]
    for i, w in enumerate(seq[1:], 1):
        rows = [w] + [seq[j] for j in range(i - 1, -1, -1)][: (i % 5)]
        wt("bytes", steps=[{"k": "comp", "pinyin": "w" * (i + 1)}, {"k": "list", "words": rows}])
        time.sleep(0.15)
    time.sleep(1.5)
    s = app.state()
    out = {"build": "packaged" if "--dev" not in sys.argv else "dev", "keystrokes": len(seq) - 1, "window_resizes": s["windowResizes"] - r0}
    wt("bytes", steps=[{"k": "commit"}])
finally:
    app.quit(); mock.stdin.close(); mock.wait(5)
print(json.dumps(out))
