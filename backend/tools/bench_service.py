"""Benchmark translation latency per model on the configured service (uses the key stored in Credential Manager;
never prints it). Streams the response to measure time to first token (TTFT) and total time, and records whether
the model emitted reasoning before the answer. Candidates are a fixed synthetic set, not user text.

Run: python -X utf8 -I backend/tools/bench_service.py <provider> <model>[,<model>…] [--rounds 3] [--extra '{"json": …}']
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from translate_backend.translate import http, providers, secrets  # noqa: E402

BATCHES = [
    {1: "时间", 2: "事件", 3: "实践", 4: "世间", 5: "试剑"},
    {1: "我们明天下午三点在会议室讨论这个问题", 2: "我们明天", 3: "我们", 4: "我"},
    {1: "谢谢你的帮助", 2: "谢谢", 3: "写写"},
]


def stream_once(svc, key, texts, extra):
    url, headers, body = providers.build(svc, key, texts, "en")
    body.update(extra)
    p = svc["protocol"]
    if p in ("openai", "anthropic", "responses"):
        body["stream"] = True
    t0 = time.perf_counter()
    ttft = None
    reasoning = False
    out = []
    import http.client as hc
    import urllib.parse as up
    u = up.urlsplit(url)
    c = hc.HTTPSConnection(u.hostname, u.port or 443, timeout=30, context=http._ssl()[1])
    hdrs = {"Content-Type": "application/json", "Accept": "text/event-stream", "User-Agent": "Translate/0.5", **headers}
    c.request("POST", u.path + (("?" + u.query) if u.query else ""), body=json.dumps(body, ensure_ascii=False).encode(), headers=hdrs)
    r = c.getresponse()
    if r.status != 200:
        return {"error": r.status, "detail": http._detail(r.read())}
    for raw in r:
        line = raw.decode("utf-8", "replace").strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            ev = json.loads(data)
        except ValueError:
            continue
        piece = ""
        if p == "openai":
            d = (ev.get("choices") or [{}])[0].get("delta") or {}
            if d.get("reasoning_content") or d.get("reasoning"):
                reasoning = True
            piece = d.get("content") or ""
        elif p == "anthropic":
            if ev.get("type") == "content_block_delta":
                dd = ev.get("delta", {})
                if dd.get("type") == "thinking_delta":
                    reasoning = True
                piece = dd.get("text", "")
        elif p == "responses":
            if ev.get("type", "").startswith("response.reasoning"):
                reasoning = True
            if ev.get("type") == "response.output_text.delta":
                piece = ev.get("delta", "")
        if piece and ttft is None:
            ttft = time.perf_counter() - t0
        out.append(piece)
    total = time.perf_counter() - t0
    text = "".join(out)
    try:
        got = providers.parse_map(text)
    except providers.HttpError:
        got = {}
    return {"ttft": ttft, "total": total, "reasoning": reasoning, "items": len(got), "want": len(texts), "out": got}


def main():
    provider, models = sys.argv[1], sys.argv[2].split(",")
    rounds = int(sys.argv[sys.argv.index("--rounds") + 1]) if "--rounds" in sys.argv else 2
    extra = json.loads(sys.argv[sys.argv.index("--extra") + 1]) if "--extra" in sys.argv else {}
    key = secrets.get_key(provider)
    if not key:
        sys.exit(f"no key stored for {provider}")
    rows = []
    for m in models:
        svc = providers.resolve({"provider": provider, "model": m})
        svc["jsonMode"] = True
        res = []
        for _ in range(rounds):
            for b in BATCHES:
                try:
                    res.append(stream_once(svc, key, b, extra))
                except Exception as e:  # noqa: BLE001
                    res.append({"error": type(e).__name__})
        ok = [r for r in res if "total" in r]
        row = {"model": m, "protocol": svc["protocol"], "ok": f"{len(ok)}/{len(res)}",
               "ttft_p50": round(statistics.median([r["ttft"] for r in ok if r["ttft"]]) * 1000) if ok else None,
               "total_p50": round(statistics.median([r["total"] for r in ok]) * 1000) if ok else None,
               "total_max": round(max(r["total"] for r in ok) * 1000) if ok else None,
               "reasoning": any(r.get("reasoning") for r in ok), "complete": all(r["items"] == r["want"] for r in ok) if ok else False,
               "errors": sorted({f"{r['error']} {r.get('detail', '')[:60]}" for r in res if "error" in r})}
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    if "--show" in sys.argv:  # sample outputs of the last model (synthetic inputs only)
        for r in ok[:3]:
            print(json.dumps(r["out"], ensure_ascii=False))


if __name__ == "__main__":
    main()
