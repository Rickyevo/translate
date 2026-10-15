"""Merge a capture with session marks and summarize: message lengths, first bytes, top-level fields,
candidate lists (decoded with the parser under test), window events.
Run from backend/:  python -X utf8 tools/wetype_analyze.py [DIR]
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from translate_backend.wetype import pb  # noqa: E402

d = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / ".cache" / "wetype")
cap = [json.loads(l) for l in open(d / "capture.jsonl", encoding="utf-8")]
marks = [json.loads(l) for l in open(d / "marks.jsonl", encoding="utf-8")] if (d / "marks.jsonl").exists() else []
events = [("mark", m["wall"], m) for m in marks] + [("cap", c["wall"], c) for c in cap]
events.sort(key=lambda e: e[1])
t0 = events[0][1]
for kind, t, e in events:
    ts = f"{(t - t0) * 1000:8.0f}ms"
    if kind == "mark":
        print(f"{ts}  === {e['mark']}")
        continue
    if e["src"] == "win":
        print(f"{ts}  win {e['event']:5} visible={e['visible']} rect={e['rect']}")
    elif e.get("t") == "w":
        b = base64.b64decode(e.get("b64", ""))
        top = [(f, wt, (len(v) if isinstance(v, (bytes, bytearray)) else v)) for f, wt, v in pb.fields(b)][:8]
        cands = pb.candidates(b)
        print(f"{ts}  pipe h={e['handle']} len={e['len']:5}{' GATED' if e.get('gated') else ''} head={b[:6].hex(' ')} top={top}" + (f"  CANDS={cands}" if cands else ""))
    elif e.get("t") == "handle":
        print(f"{ts}  handle {e['handle']} ok={e['ok']} {e.get('name', '')}")
    else:
        print(f"{ts}  {e}")
