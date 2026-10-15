"""JSON Lines over stdio. One JSON object per line, UTF-8.

stdout carries protocol messages only; diagnostics go to stderr (see log.py), so the two never mix.
Every message has "v" (protocol version) and "type". Requests from the host may carry "id";
replies echo it. See docs/protocol.md for the full contract.
"""
from __future__ import annotations

import json
import sys
import threading
from typing import Any

PROTOCOL_VERSION = 1

_out_lock = threading.Lock()
_stdout = sys.stdout.buffer


def send(msg_type: str, **fields: Any) -> None:
    """Write one message. Thread-safe; flushes so the host sees it immediately."""
    line = json.dumps({"v": PROTOCOL_VERSION, "type": msg_type, **fields}, ensure_ascii=False, separators=(",", ":"))
    data = (line + "\n").encode("utf-8")
    with _out_lock:
        _stdout.write(data)
        _stdout.flush()


def reply(req: dict, msg_type: str, **fields: Any) -> None:
    if "id" in req:
        fields["id"] = req["id"]
    send(msg_type, **fields)


def read_messages():
    """Yield decoded messages from stdin until EOF. Malformed lines are reported, not fatal."""
    for raw in sys.stdin.buffer:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw.decode("utf-8"))
            if not isinstance(msg, dict) or "type" not in msg:
                raise ValueError("message must be an object with a 'type'")
        except Exception as e:  # noqa: BLE001 — report and continue
            send("error", code="bad_message", message="Unreadable message from host", detail=str(e)[:200])
            continue
        yield msg
