"""Local mock translation service on 127.0.0.1 speaking the three wire formats (tests only, no network).

Translations are "T<target>(<text>)". Behaviour switches: mode = ok | auth | error | slow | garbage | refuse | drop.
Records each request's path, headers of interest and parsed body (in memory, for assertions).
"""
from __future__ import annotations

import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class MockService:
    def __init__(self):
        self.mode = "ok"
        self.delay = 0.0
        self.requests: list[dict] = []
        self.models = ["mock-a", "mock-b"]
        svc = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def _send(self, code, obj):
                data = json.dumps(obj, ensure_ascii=False).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                svc.requests.append({"method": "GET", "path": self.path, "headers": dict(self.headers)})
                if "models" in self.path:
                    if "generativelanguage" in self.path or self.path.startswith("/v1beta"):
                        return self._send(200, {"models": [{"name": "models/" + m, "supportedGenerationMethods": ["generateContent"]} for m in svc.models]})
                    return self._send(200, {"data": [{"id": m} for m in svc.models]})
                self._send(404, {})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                svc.requests.append({"method": "POST", "path": self.path, "headers": dict(self.headers), "body": body})
                if svc.mode == "drop":
                    self.close_connection = True
                    return
                if svc.delay or svc.mode == "slow":
                    time.sleep(svc.delay or 3)
                if svc.mode == "auth":
                    return self._send(401, {"error": {"message": "bad key"}})
                if svc.mode == "error":
                    return self._send(500, {"error": "boom"})
                if "/messages" in self.path:
                    sysmsg, user = body["system"], body["messages"][0]["content"]
                elif ":generateContent" in self.path:
                    sysmsg, user = body["systemInstruction"]["parts"][0]["text"], body["contents"][0]["parts"][0]["text"]
                else:
                    sysmsg, user = body["messages"][0]["content"], body["messages"][1]["content"]
                lang = re.search(r"into (\w+)\.", sysmsg).group(1)[:2].lower()
                items = json.loads(user)
                out = {k: f"T{lang}({v})" for k, v in items.items()}
                text = "not json at all" if svc.mode == "garbage" else "```json\n" + json.dumps(out, ensure_ascii=False) + "\n```"
                if "/messages" in self.path:
                    if svc.mode == "refuse":
                        return self._send(200, {"content": [], "stop_reason": "refusal"})
                    return self._send(200, {"content": [{"type": "text", "text": text}], "stop_reason": "end_turn"})
                if ":generateContent" in self.path:
                    return self._send(200, {"candidates": [{"content": {"parts": [{"text": "thinking…", "thought": True}, {"text": text}]}}]})
                self._send(200, {"choices": [{"message": {"content": text}}]})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.server.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def posts(self):
        return [r for r in self.requests if r["method"] == "POST"]

    def close(self):
        self.server.shutdown()
        self.server.server_close()


if __name__ == "__main__":  # standalone for the app-level test: prints its URL, serves until stdin closes
    import sys
    m = MockService()
    print(json.dumps({"url": m.url}), flush=True)
    for line in sys.stdin:
        cmd = json.loads(line)
        if "mode" in cmd:
            m.mode = cmd["mode"]
        if "delay" in cmd:
            m.delay = float(cmd["delay"])
        if "models" in cmd:
            m.models = [f"vendor-model-{i:02d}-{'long-name-' * (i % 3)}x" for i in range(int(cmd["models"]))]
        print(json.dumps({"posts": len(m.posts()), "last_auth": (m.posts()[-1]["headers"].get("Authorization", "")[:7] if m.posts() else "")}), flush=True)
