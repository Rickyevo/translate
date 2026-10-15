"""Print the protobuf field tree of selected captured messages (lengths, ints, short strings).
Run from backend/:  python -X utf8 tools/wetype_tree.py [N_SMALL] [N_LIST]
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from translate_backend.wetype import pb  # noqa: E402

d = Path(__file__).resolve().parents[2] / ".cache" / "wetype"
msgs = [base64.b64decode(c["b64"]) for c in (json.loads(l) for l in open(d / "capture.jsonl", encoding="utf-8")) if c.get("t") == "w" and c.get("b64")]


def show(b: bytes, depth=0, maxdepth=7):
    for f, wt, v in pb.fields(b):
        pad = "  " * depth
        if wt == 2:
            v = bytes(v)
            try:
                s = v.decode("utf-8")
                printable = all(ch.isprintable() for ch in s) and len(s) < 60
            except UnicodeDecodeError:
                printable = False
            sub = pb.fields(v)
            # treat as submessage if it parses fully into plausible fields
            if depth < maxdepth and sub and not printable:
                print(f"{pad}{f}: <msg {len(v)}>")
                show(v, depth + 1, maxdepth)
            else:
                print(f"{pad}{f}: {s!r}" if printable else f"{pad}{f}: <bytes {len(v)}> {v[:16].hex()}")
        else:
            print(f"{pad}{f}: {v}")


small = [m for m in msgs if len(m) < 130]
lists = [m for m in msgs if pb.candidates(m)]
others = [m for m in msgs if len(m) >= 130 and not pb.candidates(m)]
print(f"{len(msgs)} msgs: {len(small)} small, {len(lists)} lists, {len(others)} other")
for m in small[:3] + [s for s in small if len(s) > 60][:2] + [s for s in small if len(s) < 25][:4]:
    print("=== small", len(m))
    show(m)
print("=== list", len(lists[-1]))
show(lists[-1], maxdepth=5)
for m in others[:2]:
    print("=== other", len(m))
    show(m, maxdepth=4)
