"""Launch the Translate app (dev build or packaged exe) with the test-control endpoint, and talk to it."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

APP = Path(__file__).resolve().parents[2]
ROOT = APP.parent
DEV_ELECTRON = APP / "node_modules" / "electron" / "dist" / "electron.exe"
# TRANSLATE_EXE overrides the packaged build under test (e.g. out-next/ while out/ is in use).
PACKAGED = Path(os.environ["TRANSLATE_EXE"]) if os.environ.get("TRANSLATE_EXE") else APP / "out" / "Translate-win32-x64" / "Translate.exe"


class App:
    def __init__(self, port: int = 47321, packaged: bool = False, extra_args: list[str] | None = None, env: dict | None = None):
        self.port = port
        exe = PACKAGED if packaged else DEV_ELECTRON
        args = [str(exe)] + ([] if packaged else [str(APP)]) + [f"--test-control={port}"] + (extra_args or [])
        e = {**os.environ, "TRANSLATE_PYTHON": sys.executable, **(env or {})}
        # Isolated user data so tests never touch the user's real config.
        e["TRANSLATE_USER_DATA"] = str(ROOT / ".cache" / "test-userdata")
        self.proc = subprocess.Popen(args, env=e, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.pid = self.proc.pid
        self._wait_ready()

    def call(self, path: str, body: dict | None = None, timeout: float = 5):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=json.dumps(body or {}).encode(), method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"null")

    def state(self):
        return self.call("/state")

    def _wait_ready(self, timeout: float = 20):
        end = time.time() + timeout
        while time.time() < end:
            try:
                s = self.state()
                if s.get("backendPid"):
                    time.sleep(0.5)
                    return
            except Exception:  # noqa: BLE001 — not listening yet
                pass
            time.sleep(0.2)
        raise TimeoutError("app did not start")

    def wait(self, pred, timeout: float = 5, step: float = 0.05):
        end = time.time() + timeout
        last = None
        while time.time() < end:
            last = self.state()
            if pred(last):
                return last
            time.sleep(step)
        raise TimeoutError(f"condition not met; last state: {json.dumps(last)[:400]}")

    def quit(self):
        try:
            self.call("/quit", timeout=2)
        except Exception:  # noqa: BLE001
            pass
        try:
            self.proc.wait(5)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(self.pid)], capture_output=True)
