"""Minimal protobuf wire-format reader (no schema, no dependencies) for WeType renderer messages.

Only what we need: iterate fields, descend into length-delimited submessages. Malformed input never
raises out of these helpers — they stop at the first inconsistency and return what was read.
"""
from __future__ import annotations

from typing import Iterator


def varint(b: bytes, i: int) -> tuple[int, int]:
    r = s = 0
    while True:
        if i >= len(b) or s > 63:
            raise ValueError("truncated varint")
        x = b[i]
        i += 1
        r |= (x & 0x7F) << s
        if not x & 0x80:
            return r, i
        s += 7


def fields(b: bytes) -> list[tuple[int, int, object]]:
    """(field number, wire type, value) — value is int for varint/fixed, bytes for length-delimited."""
    out: list[tuple[int, int, object]] = []
    i = 0
    try:
        while i < len(b):
            tag, i = varint(b, i)
            fn, wt = tag >> 3, tag & 7
            if fn == 0:
                break
            if wt == 0:
                v, i = varint(b, i)
                out.append((fn, 0, v))
            elif wt == 2:
                n, i = varint(b, i)
                if n < 0 or i + n > len(b):
                    break
                out.append((fn, 2, b[i : i + n]))
                i += n
            elif wt == 5:
                out.append((fn, 5, int.from_bytes(b[i : i + 4], "little")))
                i += 4
            elif wt == 1:
                out.append((fn, 1, int.from_bytes(b[i : i + 8], "little")))
                i += 8
            else:
                break
    except ValueError:
        pass
    return out


def sub(b: bytes, *path: int) -> bytes | None:
    """Descend through length-delimited fields by number (first match at each level)."""
    cur: bytes | None = b
    for fn in path:
        if cur is None:
            return None
        cur = next((v for f, wt, v in fields(cur) if f == fn and wt == 2), None)  # type: ignore[misc]
    return cur


def candidates(msg: bytes) -> list[str]:
    """Candidate texts in display order, or [] if this message is not a candidate list.

    Layout observed on WeType 2.1.4.6 (docs/wetype-adapter.md): message starts 08 01 12; the list is
    at field 2 → 2 → 2, as repeated field 1 entries whose field 1 is the UTF-8 candidate text.
    """
    if len(msg) < 3 or msg[0] != 0x08 or msg[1] != 0x01 or msg[2] != 0x12:
        return []
    lst = sub(msg, 2, 2, 2)
    if not lst:
        return []
    out: list[str] = []
    for f, wt, item in fields(lst):
        if f != 1 or wt != 2:
            continue
        text = next((v for f2, wt2, v in fields(item) if f2 == 1 and wt2 == 2), None)  # type: ignore[arg-type]
        if text is not None:
            try:
                out.append(bytes(text).decode("utf-8"))
            except UnicodeDecodeError:
                pass
    return out
