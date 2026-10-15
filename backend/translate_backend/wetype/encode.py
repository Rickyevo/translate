"""Synthetic WeType session-channel messages, the inverse of protocol.decode().

Used by the unit tests and by the replay source (test mode only) to drive the real framing, decoding and
state machine without attaching to the IME. Layouts match the observations documented in protocol.py.
"""
from __future__ import annotations


def _varint(n: int) -> bytes:
    out = bytearray()
    while n > 127:
        out.append((n & 127) | 128)
        n >>= 7
    return bytes(out) + bytes([n])


def _value(field: int, n: int) -> bytes:
    return _varint(field << 3) + _varint(n)


def _sub(field: int, data: bytes) -> bytes:
    return _varint((field << 3) | 2) + _varint(len(data)) + data


def event(kind: int, body: bytes = b"", session: int = 123) -> bytes:
    return _value(1, 1) + _sub(2, _value(1, session) + _sub(2, _value(1, kind) + body))


def composition(pinyin: str) -> bytes:
    """Composition update; "" encodes the 'cleared' form (no segments)."""
    if not pinyin:
        return event(3)
    segs = b""
    for i, part in enumerate(pinyin.split("'")):
        if i:
            segs += _sub(1, _value(1, 6))
        segs += _sub(1, _value(1, 1) + _sub(7, part.encode()))
    return event(3, _sub(3, segs))


def candidates(words: list[str]) -> bytes:
    return event(2, _sub(2, b"".join(_sub(1, _sub(1, w.encode())) for w in words)))


def commit() -> bytes:
    return event(1, _sub(4, b"committed"))


def build(steps: list[dict]) -> bytes:
    """[{"k": "comp", "pinyin": "shi"}, {"k": "list", "words": [...]}, {"k": "commit"}, {"k": "other", "kind": 12}]"""
    out = b""
    for s in steps:
        k = s.get("k")
        if k == "comp":
            out += composition(str(s.get("pinyin", "")))
        elif k == "list":
            out += candidates([str(w) for w in s.get("words", [])])
        elif k == "commit":
            out += commit()
        elif k == "other":
            out += event(int(s.get("kind", 12)))
        elif k == "junk":
            out += bytes(s.get("data", b"\x00\xff\x13"))
    return out
