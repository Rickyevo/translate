"""Short read-only connection check. Prints status/counts only; no text files or input injection."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

backend = Path(__file__).resolve().parents[1]
proc = subprocess.Popen([sys.executable, "-E", "-s", "-B", "-m", "translate_backend"],
                        cwd=backend, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, text=True, encoding="utf-8",
                        env={**os.environ, "PYTHONUTF8": "1"}, creationflags=0x08000000)
events = queue.Queue()
def pump():
    for line in proc.stdout:
        try:
            # Immediately reduce to non-content metadata.
            msg = json.loads(line)
            events.put({"type": msg.get("type"), "ime": msg.get("ime"),
                        "adapters": msg.get("adapters"), "code": msg.get("code")})
        except ValueError:
            events.put({"type": "invalid"})
threading.Thread(target=pump, daemon=True).start()
def send(t, **fields):
    proc.stdin.write(json.dumps({"v": 1, "type": t, **fields}) + "\n")
    proc.stdin.flush()
counts, states = {}, []
try:
    send("config.set", config={"target": "en", "count": 5, "localOnly": True, "denylist": []})
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            m = events.get(timeout=.2)
        except queue.Empty:
            continue
        counts[m["type"]] = counts.get(m["type"], 0) + 1
        if m.get("ime"):
            states.append(m["ime"])
    send("shutdown")
    proc.stdin.close()
    proc.wait(timeout=5)
    print(json.dumps({"states": states, "message_counts": counts, "exit": proc.returncode}, ensure_ascii=False))
    sys.exit(0 if any(s.get("state") == "connected" for s in states) and proc.returncode == 0 else 1)
finally:
    if proc.poll() is None:
        proc.kill()
        proc.wait()
