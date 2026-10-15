"""Stage 5 end-to-end: the app with the real translation pipeline against a LOCAL mock service (127.0.0.1).

The app runs with the replay candidate source (synthetic IME bytes, no input injection) and --translator=live, so
cache → CC-CEDICT → service → panel run for real. Keys go through the real Settings-save path into an in-memory
key store (TRANSLATE_SECRETS=memory), never the user's Credential Manager. No external network requests.
Output: PASS/FAIL, counts, timings. Run from app/:  python -X utf8 scripts/stage5_service_test.py [--packaged]
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "harness"))
from app import ROOT, App  # noqa: E402

PACKAGED = "--packaged" in sys.argv
FG = {"hwnd": 1, "pid": 4242, "exe": "replay-target.exe"}
RECT = {"x": 60, "y": 420, "w": 470, "h": 70}
KEY = "mock-key-0123456789"
USERDATA = ROOT / ".cache" / "test-userdata"
results: list[tuple[str, bool, str]] = []
timings: dict[str, list[float]] = {}


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""), flush=True)


class Mock:
    def __init__(self):
        self.p = subprocess.Popen([sys.executable, "-X", "utf8", str(ROOT / "backend" / "tests" / "mockservice.py")],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8")
        self.url = json.loads(self.p.stdout.readline())["url"]

    def cmd(self, **c):
        self.p.stdin.write(json.dumps(c) + "\n")
        self.p.stdin.flush()
        return json.loads(self.p.stdout.readline())

    def close(self):
        self.p.stdin.close()
        self.p.wait(5)


def svc(mock_url, **over):
    return {"custom": {"protocol": "openai", "endpoint": mock_url + "/v1", "model": "mock-a", "auth": "bearer", **over}}


def run(app: App, mock: Mock):
    wt = lambda t, **f: app.call("/wetype", {"t": t, "f": f})  # noqa: E731
    wt("connection", state="connected")
    wt("window", rect=RECT, foreground=FG)
    vis = lambda s: bool(s["panel"] and s["panel"]["visible"])  # noqa: E731
    settled = lambda g: (lambda s: s["list"] and s["list"]["gen"] == g and "loading" not in s["list"]["states"])  # noqa: E731

    # No key yet: dictionary only, footer says so.
    app.call("/settings/save", {"provider": "custom", "services": svc(mock.url), "localDict": True, "localOnly": False, "timeout": 3})
    g = wt("bytes", steps=[{"k": "comp", "pinyin": "shijian"}, {"k": "list", "words": ["时间", "试剑"]}])["gen"]
    s = app.wait(settled(g), 4)
    check("no key: dictionary word translated, others 'no entry', footer 'no service'",
          s["list"]["states"] == ["done", "noEntry"] and s["sources"][0] == "dict" and s["list"]["banner"] == "noService", f"{s['list']['states']} {s['list']['banner']}")
    wt("bytes", steps=[{"k": "commit"}])

    # Save a key through the real Save path.
    app.call("/settings/save", {"apiKey": KEY})
    cfg = (USERDATA / "config.json").read_text(encoding="utf-8")
    check("config.json never contains the key", KEY not in cfg and '"apiKey"' not in cfg)
    t0 = time.perf_counter()
    g = wt("bytes", steps=[{"k": "comp", "pinyin": "shijian"}, {"k": "list", "words": ["时间", "试剑", "我们明天下午三点开会"]}])["gen"]
    s = app.wait(lambda s: settled(g)(s) and s["sources"][0] == "ai", 5)  # dictionary gloss refined by the service
    timings.setdefault("service_fill_ms", []).append(round((time.perf_counter() - t0) * 1000))
    st = mock.cmd()
    check("service fills the rest in one batch; footer back to the language switch",
          s["list"]["states"] == ["done"] * 3 and s["sources"] == ["ai", "ai", "ai"] and s["list"]["banner"] is None and st["posts"] == 1, f"sources={s['sources']} posts={st['posts']}")
    check("request authenticated with the saved key (Bearer)", st["last_auth"] == "Bearer ")
    wt("bytes", steps=[{"k": "commit"}])

    # Cache: the same list again is answered locally.
    g = wt("bytes", steps=[{"k": "comp", "pinyin": "shijian"}, {"k": "list", "words": ["时间", "试剑", "我们明天下午三点开会"]}])["gen"]
    s = app.wait(settled(g), 3)
    check("repeat list served from cache, no new request", s["sources"] == ["cache", "cache", "cache"] and mock.cmd()["posts"] == 1, f"{s['sources']}")
    wt("bytes", steps=[{"k": "commit"}])

    # Fast typing: one request per pause.
    before = mock.cmd()["posts"]
    for i in range(8):
        g = wt("bytes", steps=[{"k": "comp", "pinyin": "x" * (i + 1)}, {"k": "list", "words": [f"新词{i}", f"另{i}"]}])["gen"]
        time.sleep(0.04)
    s = app.wait(settled(g), 5)
    sent = mock.cmd()["posts"] - before
    check("fast typing (8 keys, 40 ms apart): one service request", sent == 1 and s["list"]["states"] == ["done", "done"], f"requests={sent}")
    wt("bytes", steps=[{"k": "commit"}])

    # Key rejected → footer, failed rows, Retry recovers.
    mock.cmd(mode="auth")
    g = wt("bytes", steps=[{"k": "comp", "pinyin": "a"}, {"k": "list", "words": ["错词一"]}])["gen"]
    s = app.wait(lambda s: settled(g)(s) and s["list"]["banner"] == "auth", 4)
    check("key rejected: row failed (auth), footer 'key rejected'", s["list"]["states"] == ["failed"] and s["reasons"] == ["auth"])
    mock.cmd(mode="ok")
    app.call("/retry", {"n": 1})
    s = app.wait(lambda s: s["list"]["states"] == ["done"] and s["list"]["banner"] is None, 4)
    check("Retry translates the row and clears the footer", s["sources"] == ["ai"])
    wt("bytes", steps=[{"k": "commit"}])

    # Unreachable → offline; dictionary words still work.
    app.call("/settings/save", {"services": {"custom": {**svc(mock.url)["custom"], "endpoint": "http://127.0.0.1:9/v1"}}})
    g = wt("bytes", steps=[{"k": "comp", "pinyin": "b"}, {"k": "list", "words": ["明天", "离线词"]}])["gen"]
    s = app.wait(lambda s: settled(g)(s) and s["list"]["banner"] == "offline", 6)
    check("unreachable service: footer 'offline', dictionary word still translated", s["list"]["states"] == ["done", "failed"] and s["reasons"][1] == "network")
    wt("bytes", steps=[{"k": "commit"}])

    # Local-only mode: nothing sent.
    app.call("/settings/save", {"services": svc(mock.url), "localOnly": True})
    before = mock.cmd()["posts"]
    g = wt("bytes", steps=[{"k": "comp", "pinyin": "c"}, {"k": "list", "words": ["电脑", "本地词"]}])["gen"]
    s = app.wait(settled(g), 3)
    time.sleep(0.4)
    check("local-only: dictionary only, nothing sent, footer 'local only'", s["list"]["states"] == ["done", "noEntry"] and s["list"]["banner"] == "localOnly" and mock.cmd()["posts"] == before)
    wt("bytes", steps=[{"k": "commit"}])
    app.call("/settings/save", {"localOnly": False})

    # Other wire formats through the settings Test connection path.
    for proto, path, auth in (("anthropic", "", "x-api-key"), ("gemini", "/v1beta", "x-goog-api-key"), ("openai", "/v1", "bearer")):
        r = app.call("/svc-test", {"service": {"provider": "custom", "protocol": proto, "endpoint": mock.url + path, "model": "mock-a", "auth": auth}, "key": "typed"}, timeout=30)
        check(f"Test connection ({proto})", r.get("ok"), f"{r.get('ms')} ms")
    r = app.call("/svc-models", {"service": {"provider": "custom", "protocol": "openai", "endpoint": mock.url + "/v1", "model": "x", "auth": "bearer"}}, timeout=30)
    check("Load models", r.get("models") == ["mock-a", "mock-b"])

    # Target language: Japanese has no dictionary step.
    app.call("/settings/save", {"target": "ja"})
    g = wt("bytes", steps=[{"k": "comp", "pinyin": "d"}, {"k": "list", "words": ["时间"]}])["gen"]
    s = app.wait(settled(g), 4)
    check("Japanese target: translated by the service", s["sources"] == ["ai"])
    wt("bytes", steps=[{"k": "commit"}])
    app.call("/settings/save", {"target": "en"})

    st = app.call("/cache")
    check("persistent cache holds only dictionary vocabulary", st["count"] >= 1 and st["count"] < st["memory"], f"disk={st['count']} memory={st['memory']}")


def main() -> int:
    shutil.rmtree(USERDATA, ignore_errors=True)
    mock = Mock()
    env = {"TRANSLATE_SECRETS": "memory"}
    app = App(port=47371, packaged=PACKAGED, extra_args=["--test-source=wetype-replay", "--translator=live"], env=env)
    try:
        run(app, mock)
        # Restart: the encrypted cache survives, the session-only entries don't.
        time.sleep(5.5)  # cache save is debounced 5 s
    except Exception as e:  # noqa: BLE001
        check("harness completed", False, f"{type(e).__name__}: {str(e)[:300]}")
    finally:
        app.quit()
    try:
        app = App(port=47372, packaged=PACKAGED, extra_args=["--test-source=wetype-replay", "--translator=live"], env=env)
        mock.cmd(mode="error")
        wt = lambda t, **f: app.call("/wetype", {"t": t, "f": f})  # noqa: E731
        wt("connection", state="connected")
        wt("window", rect=RECT, foreground=FG)
        app.call("/settings/save", {"apiKey": KEY, "target": "ja"})  # 时间 → Japanese was persisted (dictionary vocabulary)
        g = wt("bytes", steps=[{"k": "comp", "pinyin": "e"}, {"k": "list", "words": ["时间", "我们明天下午三点开会"]}])["gen"]
        s = app.wait(lambda s: s["list"] and s["list"]["gen"] == g and "loading" not in s["list"]["states"], 5)
        check("after restart: dictionary-word translation from the encrypted disk cache, sentence not persisted",
              s["sources"][0] == "cache" and s["list"]["states"][1] == "failed", f"{s['sources']} {s['list']['states']}")
        raw = (USERDATA / "cache" / "translations.bin").read_bytes()
        check("cache file is encrypted (no plaintext)", "时间".encode() not in raw and b"Tja(" not in raw)
        log = (USERDATA / "logs" / "translate.log").read_text(encoding="utf-8")
        check("log has no key and no candidate text", KEY not in log and "试剑" not in log and "时间" not in log)
    except Exception as e:  # noqa: BLE001
        check("restart phase completed", False, f"{type(e).__name__}: {str(e)[:300]}")
    finally:
        app.quit()
        mock.close()
    passed = sum(ok for _, ok, _ in results)
    summary = {"build": "packaged" if PACKAGED else "dev", "passed": passed, "total": len(results), "timings_ms": timings,
               "failed": [n for n, ok, _ in results if not ok]}
    out = ROOT / "measurements" / "stage5"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"service-{summary['build']}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
