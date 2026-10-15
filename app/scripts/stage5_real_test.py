"""Stage 5 acceptance against the REAL translation service you configured (no keyboard/mouse input).

The packaged app runs with the replay candidate source (synthetic candidates — never your typing) and the real
pipeline, using your saved provider/model settings (copied from %APPDATA%\\Translate\\config.json, no key in it) and
the key you stored in Windows Credential Manager (read by the app; never by this script).

Measures: accuracy on a fixed word/phrase/sentence set (accepted-meaning keywords), Japanese/Korean output script,
response time (cold connection vs warm), long candidates + lead preview, continuous typing (requests, placeholder
churn, time to final translation), cache reuse, and the insertion sequence (recorded, not typed).
Output: summary JSON in measurements/stage5/real-*.json (synthetic texts and their translations only).
Run from app/:  python -X utf8 scripts/stage5_real_test.py [--model <id>] [--no-dict-pass]
"""
from __future__ import annotations

import json
import os
import re
import shutil
import statistics
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "harness"))
from app import ROOT, App  # noqa: E402

USERDATA = ROOT / ".cache" / "test-userdata"
FG = {"hwnd": 1, "pid": 4242, "exe": "replay-target.exe"}
RECT = {"x": 900, "y": 300, "w": 470, "h": 70}

SHORT = [
    ("时间", "time"), ("事件", "event|incident"), ("实践", "practice"), ("会议室", "meeting room|conference room"),
    ("明天", "tomorrow"), ("谢谢", "thank"), ("你好", "hello|hi"), ("电脑", "computer"), ("手机", "phone|mobile"),
    ("飞机", "plane|aircraft"), ("天气", "weather"), ("朋友", "friend"), ("工作", "work|job"), ("学习", "stud|learn"),
    ("问题", "question|problem|issue"), ("数据", "data"), ("翻译", "translat"), ("输入法", "input method|ime"),
    ("公司", "company|firm"), ("医院", "hospital"), ("苹果", "apple"), ("咖啡", "coffee"), ("银行", "bank"),
    ("机场", "airport"), ("周末", "weekend"), ("生日快乐", "happy birthday"),
    ("没关系", "ok|okay|no problem|matter|mind|fine|alright|all right|worries"),
    ("加油", "come on|go for it|keep it up|you can do it|keep going|cheer|fighting|good luck"),
    ("不客气", "welcome|no problem|not at all|mention|pleasure"), ("试剑", "sword"),
]
LONG = [
    ("我们明天下午三点在会议室讨论这个问题", ["tomorrow", "3|three", "meeting|conference", "discuss"]),
    ("请大家提前准备好上周的数据", ["prepar|ready", "last week|previous week", "data"]),
    ("这个问题我们明天再讨论", ["tomorrow", "discuss|talk", "question|issue|problem|matter|this"]),
    ("我已经把文件发到你的邮箱了", ["file|document", "email|mailbox|inbox", "sent|send"]),
    ("今天天气很好我们去公园散步吧", ["weather", "park", "walk|stroll"]),
    ("如果你有任何问题请随时联系我", ["question|problem|issue", "contact|reach", "any time|anytime|feel free|free to|at any"]),
]
CJK = re.compile(r"[㐀-鿿]")
results: list[tuple[str, bool, str]] = []
report: dict = {}


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""), flush=True)


def ok_short(tr: str, accept: str) -> bool:
    return bool(tr) and not CJK.search(tr) and any(a in tr.lower() for a in accept.split("|"))


def ok_long(tr: str, needs: list[str]) -> bool:
    return bool(tr) and not CJK.search(tr) and all(any(a in tr.lower() for a in n.split("|")) for n in needs)


class Run:
    def __init__(self, app: App):
        self.a = app
        self.k = 0

    def wt(self, t, **f):
        return self.a.call("/wetype", {"t": t, "f": f}, timeout=10)

    def show(self, words, settle=20.0, refined=False):
        """New composition with this list; returns (translations, seconds until every row settled). With refined,
        also waits (≤ 6 s) for dictionary glosses to be replaced by the service, and records that time."""
        self.k += 1
        self.wt("bytes", steps=[{"k": "commit"}])
        t0 = time.perf_counter()
        g = self.wt("bytes", steps=[{"k": "comp", "pinyin": "p" + "x" * (self.k % 9)}, {"k": "list", "words": words}])["gen"]
        s = self.a.wait(lambda s: s["list"] and s["list"]["gen"] == g and "loading" not in s["list"]["states"], settle, 0.02)
        dt = time.perf_counter() - t0
        if refined:
            end = time.perf_counter() + 6
            while time.perf_counter() < end and any(x == "dict" for x in (self.a.state()["sources"] or [])):
                time.sleep(0.03)
            report.setdefault("refine_s", []).append(round(time.perf_counter() - t0, 2))
        return self.a.call("/translations"), dt, s


def service_lines():
    log = USERDATA / "logs" / "translate.log"
    return re.findall(r"backend: service (ok|error) [^\n]*?\bms=(\d+)", log.read_text(encoding="utf-8")) if log.exists() else []


def main() -> int:
    args = sys.argv[1:]
    user_cfg = json.loads((Path(os.environ["APPDATA"]) / "Translate" / "config.json").read_text(encoding="utf-8"))
    provider = user_cfg.get("provider", "openai")
    services = user_cfg.get("services") or {}
    if "--model" in args:
        services = {**services, provider: {**services.get(provider, {}), "model": args[args.index("--model") + 1]}}
    model = (services.get(provider) or {}).get("model") or "(preset default)"
    shutil.rmtree(USERDATA, ignore_errors=True)
    USERDATA.mkdir(parents=True)
    base = {"provider": provider, "services": services, "timeout": 15, "target": "en", "localDict": True, "localOnly": False}
    (USERDATA / "config.json").write_text(json.dumps(base), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "TRANSLATE_SECRETS"}  # the real vault: your stored key
    app = App(port=47401, packaged=True, extra_args=["--test-source=wetype-replay", "--translator=live"], env=env)
    r = Run(app)
    report.update({"provider": provider, "model": model})
    try:
        r.wt("connection", state="connected")
        r.wt("window", rect=RECT, foreground=FG)

        # 1. Short candidates as shipped (dictionary first, service for the rest), then service-only.
        for label, dict_on in (("as shipped (dictionary + service)", True), ("service only", False)):
            if not dict_on:
                if "--no-dict-pass" in args:
                    continue
                app.call("/settings/save", {"localDict": False})
                app.call("/cache", {"clear": True})
            hits, times, src = 0, [], {}
            for i in range(0, len(SHORT), 5):
                chunk = SHORT[i:i + 5]
                tr, dt, _ = r.show([w for w, _ in chunk], refined=dict_on)
                times.append(dt)
                for (w, acc), t in zip(chunk, tr):
                    good = ok_short(t["translation"] or "", acc)
                    hits += good
                    src[t["source"]] = src.get(t["source"], 0) + 1
                    report.setdefault("short_" + ("dict" if dict_on else "svc"), []).append({"zh": w, "en": t["translation"], "ok": good, "source": t["source"]})
            acc_pct = round(100 * hits / len(SHORT))
            check(f"short candidates, {label}: accuracy ≥ 90 %", acc_pct >= 90, f"{hits}/{len(SHORT)} = {acc_pct} %, sources={src}")
            report[f"short_time_{'dict' if dict_on else 'svc'}_s"] = [round(x, 2) for x in times]
        app.call("/settings/save", {"localDict": True})

        # 2. Long candidates (sentences) and the lead preview.
        hits = 0
        long_times = []
        for i in range(0, len(LONG), 3):
            chunk = LONG[i:i + 3]
            tr, dt, s = r.show([w for w, _ in chunk])
            long_times.append(dt)
            for (w, needs), t in zip(chunk, tr):
                good = ok_long(t["translation"] or "", needs)
                hits += good
                report.setdefault("long", []).append({"zh": w, "en": t["translation"], "ok": good})
            time.sleep(0.5)
            pv = app.state()["preview"]
            check(f"long candidate #1 opens the lead preview ({i // 3 + 1})", pv is not None, pv and pv["kind"])
        check("long candidates: all meaning keywords present (≥ 5 of 6)", hits >= 5, f"{hits}/{len(LONG)}")
        report["long_time_s"] = [round(x, 2) for x in long_times]

        # 3. Response time: cold connection (after > 60 s idle would be realistic; here: fresh app) vs warm.
        lines = service_lines()
        ms = [int(m) for _, m in lines]
        report["service_ms_all"] = ms
        if ms:
            report["service_ms_p50"] = statistics.median(ms)
            report["service_ms_p95"] = sorted(ms)[int(0.95 * (len(ms) - 1))]
        check("service response time p50 ≤ 2 s", ms and statistics.median(ms) <= 2000, f"p50={report.get('service_ms_p50')} ms p95={report.get('service_ms_p95')} ms over {len(ms)} requests")
        errs = [l for l in lines if l[0] == "error"]
        check("no service errors", not errs, f"{len(errs)} errors")

        # 4. Cache reuse: the same list again, answered locally with no request.
        before = len(service_lines())
        tr, dt, _ = r.show([w for w, _ in SHORT[25:30]])
        report["cache_list_s"] = round(dt, 3)
        check("cache reuse: repeated list from cache, no request, < 0.3 s", all(t["source"] in ("cache", "dict") for t in tr) and len(service_lines()) == before and dt < 0.3,
              f"sources={[t['source'] for t in tr]} time={dt * 1000:.0f} ms")

        # 5. Continuous typing: 12 keystrokes, 150 ms apart, one composition, new candidates every time.
        r.wt("bytes", steps=[{"k": "commit"}])
        before = len(service_lines())
        sentence = "我们下周一上午十点开会讨论新项目的预算"
        samples, stop = [], threading.Event()

        def sample():
            while not stop.is_set():
                s = app.state()
                if s["list"]:
                    stale = s.get("stale") or [False] * len(s["list"]["states"])
                    samples.append([st == "loading" and not sl for st, sl in zip(s["list"]["states"], stale)])
                time.sleep(0.015)

        th = threading.Thread(target=sample)
        th.start()
        for i in range(1, 13):
            words = [sentence[: 3 + i], sentence[: 2 + i], sentence[:4], "我们"]
            g = r.wt("bytes", steps=[{"k": "comp", "pinyin": "w" * i}, {"k": "list", "words": words}])["gen"]
            time.sleep(0.15)
        t_last = time.perf_counter()
        s = app.wait(lambda s: s["list"] and s["list"]["gen"] == g and "loading" not in s["list"]["states"], 20, 0.02)
        final_s = time.perf_counter() - t_last
        time.sleep(0.3)
        stop.set()
        th.join()
        reqs = len(service_lines()) - before
        tr = app.call("/translations")
        # Flicker = a row that showed text going back to a blank placeholder (not rows still waiting for their first text).
        flips = sum(1 for row in range(4) for a, b in zip(samples, samples[1:]) if row < len(a) and row < len(b) and not a[row] and b[row])
        report["typing"] = {"requests": reqs, "final_after_last_key_s": round(final_s, 2), "text_to_placeholder_flips": flips,
                            "final": [t["translation"] for t in tr]}
        check("continuous typing: ≤ 4 requests for 12 keystrokes", reqs <= 4, f"requests={reqs}")
        check("continuous typing: final list translated ≤ 3.5 s after the last key", final_s <= 3.5, f"{final_s:.2f} s")
        check("continuous typing: no row flips from text back to a placeholder", flips == 0, f"flips={flips}")
        check("continuous typing: final candidate translated sensibly", ok_long(tr[0]["translation"] or "", ["monday", "10|ten", "meet", "project"]), tr[0]["translation"] or "")

        # 6. Insertion sequence (dry): Esc first, then exactly the translation shown in row 1.
        app.call("/input", {"clear": True, "onEscape": "clear"})
        shown = tr[0]["translation"]
        res = app.call("/insert", {"n": 1})
        log = app.call("/input", {"clear": True})["log"]
        check("insert row 1: Esc, then the shown translation typed", res.get("ok") and log[0].get("key") == 0x1B and log[1].get("text") == shown)

        # 7. Japanese and Korean targets.
        for tgt, rx in (("ja", r"[぀-ヿ一-鿿]"), ("ko", r"[가-힯]")):
            app.call("/settings/save", {"target": tgt})
            tr, dt, _ = r.show(["会议室", "我们明天下午三点开会", "谢谢"])
            good = all(t["translation"] and re.search(rx, t["translation"]) for t in tr)
            report[f"target_{tgt}"] = [t["translation"] for t in tr]
            check(f"target {tgt}: output in the target script", good, f"{dt:.2f} s")
        app.call("/settings/save", {"target": "en"})
        r.wt("bytes", steps=[{"k": "commit"}])
    except Exception as e:  # noqa: BLE001
        check("harness completed", False, f"{type(e).__name__}: {str(e)[:300]}")
    finally:
        app.quit()
    passed = sum(ok for _, ok, _ in results)
    report.update({"passed": passed, "total": len(results), "failed": [n for n, ok, _ in results if not ok]})
    out = ROOT / "measurements" / "stage5"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"real-{model.replace('/', '_')}-{time.strftime('%H%M%S')}.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("provider", "model", "passed", "total", "service_ms_p50", "service_ms_p95", "typing") if k in report}, ensure_ascii=False, indent=1))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
