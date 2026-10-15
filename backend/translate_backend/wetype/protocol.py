"""WeType 2.1.4.6 session-channel messages → typed events.

Observed layout (docs/wetype-adapter.md):
    message  = { 1: 1, 2: { 1: session_id, 2: event } }     framed on the pipe as 08 01 12 <varint len> …
    event.1  = event type
      2  candidate list   event.2 = { repeated 1: item { 1: text, 2: opaque, 4: source flags } }
      3  composition      event.3 = repeated segments { 1: kind (1 pinyin, 6 separator, 7 end), 7: text }
                          no segments → composition cleared
      1  commit           event.4 = committed text
      12 / 15             session bookkeeping around a commit; treated as "composition may have ended"
Nothing here logs or stores text; callers receive it in memory only.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import pb


@dataclass
class ListEvent:
    texts: list[str]


@dataclass
class CompositionEvent:
    pinyin: str  # "" = composition cleared


@dataclass
class CommitEvent:
    pass  # committed text is deliberately not carried


@dataclass
class OtherEvent:
    kind: int


Event = ListEvent | CompositionEvent | CommitEvent | OtherEvent


class Framer:
    """Reassembles messages from pipe writes (a write may hold several messages or part of one)."""

    MAX = 1 << 22

    def __init__(self):
        self.buf = bytearray()
        self.dropped = 0

    def feed(self, data: bytes) -> list[bytes]:
        if len(self.buf) + len(data) > self.MAX + 16:
            self.buf.clear()
            self.dropped += 1
            data = data[-self.MAX:]
        self.buf += data
        out: list[bytes] = []
        while True:
            if len(self.buf) < 4:
                break
            if self.buf[0] != 0x08 or self.buf[1] != 0x01 or self.buf[2] != 0x12:
                # Out of sync: skip to the next plausible header.
                nxt = self.buf.find(b"\x08\x01\x12", 1)
                self.dropped += 1
                if nxt < 0:
                    # Preserve a possible header split across two writes.
                    keep = 2 if self.buf.endswith(b"\x08\x01") else 1 if self.buf.endswith(b"\x08") else 0
                    self.buf[:] = self.buf[-keep:] if keep else b""
                    break
                del self.buf[:nxt]
                continue
            try:
                n, off = pb.varint(bytes(self.buf[:16]), 3)
            except ValueError:
                break  # length varint incomplete; wait for more
            if n <= 0 or n > self.MAX:
                del self.buf[:3]
                self.dropped += 1
                continue
            total = off + n
            if len(self.buf) < total:
                break
            out.append(bytes(self.buf[:total]))
            del self.buf[:total]
        return out


def decode(msg: bytes) -> Event | None:
    ev = pb.sub(msg, 2, 2)
    if ev is None:
        return None
    kind = next((v for f, wt, v in pb.fields(ev) if f == 1 and wt == 0), None)
    if kind == 2:
        lst = pb.sub(ev, 2) or b""
        texts: list[str] = []
        for f, wt, item in pb.fields(lst):
            if f == 1 and wt == 2:
                t = pb.sub(bytes(item), 1)
                if t is not None:
                    try:
                        texts.append(t.decode("utf-8"))
                    except UnicodeDecodeError:
                        pass
        return ListEvent(texts)
    if kind == 3:
        segs = pb.sub(ev, 3)
        parts: list[str] = []
        if segs:
            for f, wt, seg in pb.fields(segs):
                if f == 1 and wt == 2:
                    sk = next((v for f2, w2, v in pb.fields(bytes(seg)) if f2 == 1 and w2 == 0), None)
                    st = pb.sub(bytes(seg), 7)
                    if sk == 1 and st:
                        parts.append(st.decode("utf-8", "replace"))
                    elif sk == 6:
                        parts.append("'")
        return CompositionEvent("".join(parts).strip("'"))
    if kind == 1:
        return CommitEvent()
    if isinstance(kind, int):
        return OtherEvent(kind)
    return None
