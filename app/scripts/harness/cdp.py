"""Minimal Chrome DevTools Protocol client (stdlib only) to read a value from a real Edge window."""
from __future__ import annotations

import base64
import json
import os
import socket
import struct
import urllib.request


def _ws_connect(url: str) -> socket.socket:
    assert url.startswith("ws://")
    hostport, path = url[5:].split("/", 1)
    host, port = hostport.split(":")
    s = socket.create_connection((host, int(port)), timeout=5)
    key = base64.b64encode(os.urandom(16)).decode()
    s.sendall(f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n".encode())
    resp = b""
    while b"\r\n\r\n" not in resp:
        resp += s.recv(4096)
    if b" 101 " not in resp.split(b"\r\n")[0]:
        raise ConnectionError(resp[:200])
    return s


def _send(s: socket.socket, text: str):
    data = text.encode()
    mask = os.urandom(4)
    head = bytes([0x81])
    n = len(data)
    head += bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + struct.pack(">H", n) if n < 65536 else bytes([0x80 | 127]) + struct.pack(">Q", n)
    s.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))


def _recv(s: socket.socket) -> str:
    def exact(k):
        b = b""
        while len(b) < k:
            b += s.recv(k - len(b))
        return b

    b1, b2 = exact(2)
    n = b2 & 0x7F
    if n == 126:
        n = struct.unpack(">H", exact(2))[0]
    elif n == 127:
        n = struct.unpack(">Q", exact(8))[0]
    return exact(n).decode("utf-8", "replace")


def evaluate(port: int, expr: str, url_part: str = "", await_promise: bool = False):
    targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5))
    page = next(t for t in targets if t.get("type") == "page" and url_part in t.get("url", ""))
    s = _ws_connect(page["webSocketDebuggerUrl"])
    try:
        _send(s, json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": await_promise}}))
        while True:
            msg = json.loads(_recv(s))
            if msg.get("id") == 1:
                return msg["result"]["result"].get("value")
    finally:
        s.close()
