"""Stage 5: translation service, dictionary, hybrid cache, keys. Local mock service only (127.0.0.1)."""
from pathlib import Path
import io
import json
import shutil
import sys
import time
import unittest
import uuid
import warnings

warnings.simplefilter("ignore", ResourceWarning)  # the mock server's kept-alive sockets
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mockservice import MockService
from translate_backend import protocol
from translate_backend.__main__ import Backend
from translate_backend.translate import cache as tcache, providers, secrets
from translate_backend.translate.dictionary import Dictionary

TMP = Path(__file__).resolve().parents[2] / ".cache" / "test-tmp"
FG = {"hwnd": 1, "pid": 4242, "exe": "replay-target.exe"}
RECT = {"x": 100, "y": 200, "w": 600, "h": 70}


def memory_secrets(test):
    p = patch.object(secrets, "_memory", {})
    p.start()
    test.addCleanup(p.stop)


class ProviderShapes(unittest.TestCase):
    def test_presets_and_custom(self):
        for pid in ("openai", "claude", "gemini", "grok", "opencode-go", "deepseek"):
            s = providers.resolve({"provider": pid})
            self.assertTrue(s["endpoint"].startswith("https://") and s["model"], pid)
        c = providers.resolve({"provider": "custom", "protocol": "gemini", "endpoint": "http://x/v1beta", "model": "m", "auth": "query", "authName": "key"})
        self.assertEqual((c["protocol"], c["auth"], c["authName"]), ("gemini", "query", "key"))
        # A preset's wire format can't be changed by settings.
        self.assertEqual(providers.resolve({"provider": "claude", "protocol": "openai"})["protocol"], "anthropic")

    def test_claude_request(self):
        svc = providers.resolve({"provider": "claude"})
        url, h, b = providers.build(svc, "K", {1: "时间"}, "en")
        self.assertEqual(url, "https://api.anthropic.com/v1/messages")
        self.assertEqual((h["x-api-key"], h["anthropic-version"]), ("K", "2023-06-01"))
        self.assertEqual(b["output_config"], {"effort": "low"})
        self.assertEqual((b["fallbacks"], h["anthropic-beta"]), ("default", "server-side-fallback-2026-07-01"))
        self.assertNotIn("thinking", b)
        tok = providers.resolve({"provider": "claude", "auth": "bearer"})
        _, h2, _ = providers.build(tok, "T", {1: "x"}, "en")
        self.assertEqual(h2["Authorization"], "Bearer T")
        self.assertIn("oauth-2025-04-20", h2["anthropic-beta"])
        old = providers.resolve({"provider": "claude", "model": "claude-haiku-4-5"})
        _, _, b3 = providers.build(old, "K", {1: "x"}, "en")
        self.assertNotIn("output_config", b3)
        self.assertNotIn("fallbacks", b3)

    def test_gemini_and_openai_requests(self):
        url, h, b = providers.build(providers.resolve({"provider": "gemini"}), "G", {1: "x"}, "ja")
        self.assertTrue(url.endswith("/models/gemini-flash-latest:generateContent"))
        self.assertEqual(h["x-goog-api-key"], "G")
        self.assertIn("Japanese", b["systemInstruction"]["parts"][0]["text"])
        url, h, b = providers.build(providers.resolve({"provider": "opencode-go"}), "P", {1: "x", 2: "y"}, "en")
        self.assertEqual(url, "https://opencode.ai/zen/go/v1/chat/completions")
        self.assertEqual(h["Authorization"], "Bearer P")
        self.assertEqual(json.loads(b["messages"][1]["content"]), {"1": "x", "2": "y"})
        self.assertEqual(b["response_format"], {"type": "json_object"})
        q = providers.resolve({"provider": "custom", "endpoint": "https://h/v1", "model": "m", "auth": "query", "authName": "api_key"})
        url, h, _ = providers.build(q, "Z", {1: "x"}, "en")
        self.assertTrue(url.endswith("/chat/completions?api_key=Z") and "Authorization" not in h)

    def test_opencode_go_routing_and_session(self):
        chat = providers.resolve({"provider": "opencode-go"})
        url, h, b = providers.build(chat, "P", {1: "x"}, "en")
        self.assertEqual((chat["protocol"], url), ("openai", "https://opencode.ai/zen/go/v1/chat/completions"))
        self.assertTrue(h["x-opencode-session"].startswith("translate-"))
        url2, h2, _ = providers.build(chat, "P", {1: "y"}, "en")
        self.assertEqual(h["x-opencode-session"], h2["x-opencode-session"])  # stable per app run
        msg = providers.resolve({"provider": "opencode-go", "model": "qwen3.8-flash"})
        url, h, b = providers.build(msg, "P", {1: "x"}, "en")
        self.assertEqual((msg["protocol"], url, h["x-api-key"]), ("anthropic", "https://opencode.ai/zen/go/v1/messages", "P"))
        self.assertNotIn("anthropic-beta", h)
        resp = providers.resolve({"provider": "opencode-go", "model": "gpt-6-luna"})
        url, h, b = providers.build(resp, "P", {1: "x"}, "en")
        self.assertEqual((resp["protocol"], url), ("responses", "https://opencode.ai/zen/go/v1/responses"))
        self.assertIn("instructions", b)
        self.assertEqual(providers.text_of(resp, {"output": [{"type": "reasoning"}, {"type": "message", "content": [{"type": "output_text", "text": '{"1":"x"}'}]}]}), '{"1":"x"}')
        _, h, _ = providers.build(providers.resolve({"provider": "openai"}), "K", {1: "x"}, "en")
        self.assertNotIn("x-opencode-session", h)  # only for opencode.ai

    def test_error_detail(self):
        from translate_backend.translate import http as th
        self.assertEqual(th._detail(b'{"type":"error","error":{"type":"MissingSessionID","message":"Request is missing x-opencode-session"}}'),
                         "MissingSessionID: Request is missing x-opencode-session")
        self.assertEqual(th._detail(b'{"error":{"code":"model_not_found","message":"no such model"}}'), "model_not_found: no such model")
        self.assertEqual(th._detail(b"<html>"), "")

    def test_parse_map(self):
        self.assertEqual(providers.parse_map('Sure:\n```json\n{"1": " time ", "2": "event", "x": "no", "3": ""}\n```'), {1: "time", 2: "event"})
        with self.assertRaises(providers.HttpError):
            providers.parse_map("no json")


class DictionaryTests(unittest.TestCase):
    def test_lookup(self):
        d = Dictionary()
        self.assertEqual(d.lookup("时间"), "time")
        self.assertEqual(d.lookup("我们"), "we")
        self.assertIsNone(d.lookup("试剑"))
        self.assertIsNone(d.lookup("不存在的词组啊"))
        self.assertTrue(d.is_headword("会议室"))
        self.assertFalse(d.is_headword("我们明天下午"))
        d.close()


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.dir = TMP / uuid.uuid4().hex
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_hybrid_rule(self):
        d = Dictionary()
        hw = d.is_headword
        self.assertTrue(tcache.persistable("时间", "time", hw))
        self.assertTrue(tcache.persistable("会议室", "meeting room", hw))
        self.assertFalse(tcache.persistable("我们明天下午三点", "We, at 3 p.m.", hw))  # long
        self.assertFalse(tcache.persistable("张伟伟", "Zhang Weiwei", hw))  # not dictionary vocabulary
        self.assertFalse(tcache.persistable("3点", "3 o'clock", hw))  # digits
        self.assertFalse(tcache.persistable("时间", "x" * 61, hw))

    def test_encrypted_round_trip_and_memory_only(self):
        d = Dictionary()
        c = tcache.Cache(d.is_headword)
        c.open(str(self.dir))
        c.put("en", "时间", "time")
        c.put("en", "我们明天下午三点开会", "We meet at 3 p.m. tomorrow")
        c.save()
        raw = (self.dir / "cache" / "translations.bin").read_bytes()
        self.assertNotIn("时间".encode(), raw)
        self.assertNotIn(b"time", raw)  # DPAPI-encrypted
        c2 = tcache.Cache(d.is_headword)
        c2.open(str(self.dir))
        self.assertEqual(c2.get("en", "时间"), "time")
        self.assertIsNone(c2.get("en", "我们明天下午三点开会"))  # session memory only
        self.assertEqual(c.get("en", "我们明天下午三点开会"), "We meet at 3 p.m. tomorrow")
        c2.clear()
        self.assertFalse((self.dir / "cache" / "translations.bin").exists())


class SecretTests(unittest.TestCase):
    def test_credential_manager_round_trip(self):
        name = "unittest-" + uuid.uuid4().hex[:8]
        self.assertTrue(secrets.set_key(name, "secret-value-✓"))
        try:
            self.assertEqual(secrets.get_key(name), "secret-value-✓")
        finally:
            self.assertTrue(secrets.set_key(name, ""))
        self.assertEqual(secrets.get_key(name), "")


class PipelineTests(unittest.TestCase):
    """The backend with the replay source and the real pipeline (--translator=live) against the mock service."""

    def setUp(self):
        memory_secrets(self)
        self.mock = MockService()
        self.addCleanup(self.mock.close)
        self.dir = TMP / uuid.uuid4().hex
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.out = io.BytesIO()
        p = patch.object(protocol, "_stdout", self.out)
        p.start()
        self.addCleanup(p.stop)
        with patch.object(sys, "argv", ["x", "--translator=live"]):
            self.b = Backend(True, source="wetype-replay")
        self.addCleanup(self.b.scheduler.close)
        secrets.set_key("custom", "k-test")
        self.configure()
        self.b.handle({"type": "debug.wetype.connection", "state": "connected"})
        self.b.handle({"type": "debug.wetype.window", "rect": RECT, "foreground": FG})

    def configure(self, **over):
        cfg = {"target": "en", "count": 5, "denylist": [], "localOnly": False, "localDict": True, "timeout": 2,
               "provider": "custom", "dataDir": str(self.dir),
               "services": {"custom": {"protocol": "openai", "endpoint": self.mock.url + "/v1", "model": "mock-a", "auth": "bearer"}}}
        cfg.update(over)
        self.b.handle({"type": "config.set", "config": cfg})

    def msgs(self, t=None):
        lines = [json.loads(x) for x in self.out.getvalue().decode().splitlines()]
        return [m for m in lines if t is None or m["type"] == t]

    def pump(self, seconds=0.6, until=None):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if until and until():
                return
            try:
                m = self.b._backlog.popleft() if self.b._backlog else self.b.events.get(timeout=0.02)
            except Exception:
                continue
            if m is None:
                continue
            t = m["type"]
            if t == "_source":
                self.b.source.accept(m["event"])
            elif t in ("_svc_flush", "_svc_result", "_svc_hedge", "_cache_save"):
                self.b.pipeline.accept(m)
            else:
                self.b.handle(m)

    def compose(self, pinyin, words):
        self.b.handle({"type": "debug.wetype.bytes", "steps": [{"k": "comp", "pinyin": pinyin}, {"k": "list", "words": words}]})
        return self.b.source.current

    def svc_state(self):
        return [m for m in self.msgs("status") if "service" in m][-1]["service"]["state"]

    def tr(self, gen):
        return {m["n"]: m for m in self.msgs("translation") if m["gen"] == gen}

    def settled(self, cl):
        return lambda: all(i.state != "loading" for i in cl.items)

    def test_dictionary_then_service_batch(self):
        cl = self.compose("shijian", ["时间", "试剑", "我们明天"])
        t = self.tr(cl.gen)
        self.assertEqual((t[1]["text"], t[1]["source"]), ("time", "dict"))  # instant, offline
        self.pump(2, self.settled(cl))
        t = self.tr(cl.gen)
        self.assertEqual((t[2]["text"], t[2]["source"]), ("Ten(试剑)", "ai"))
        self.assertEqual(t[3]["text"], "Ten(我们明天)")
        self.assertEqual(len(self.mock.posts()), 1)  # one batch for all three
        # The dictionary hit rides along and is refined by the service (no extra request).
        self.assertEqual(json.loads(self.mock.posts()[0]["body"]["messages"][1]["content"]), {"1": "时间", "2": "试剑", "3": "我们明天"})
        self.assertEqual([m["source"] for m in self.msgs("translation") if m["gen"] == cl.gen and m["n"] == 1], ["dict", "ai"])
        self.assertEqual(self.mock.posts()[0]["headers"]["Authorization"], "Bearer k-test")
        self.assertEqual(self.svc_state(), "ok")

    def test_fast_typing_one_request_per_pause(self):
        for i in range(6):
            cl = self.compose("x" * (i + 1), ["词%d" % i, "语%d" % i])
            self.pump(0.03)
        self.pump(2, self.settled(cl))
        self.assertEqual(len(self.mock.posts()), 1)
        self.assertTrue(all(i.state == "done" for i in cl.items))

    def test_cache_reuse_and_hybrid_persistence(self):
        self.configure(target="ja")
        cl = self.compose("shijian", ["时间", "我们明天下午三点开会"])
        self.pump(2, self.settled(cl))
        self.b.handle({"type": "debug.wetype.bytes", "steps": [{"k": "commit"}]})
        cl = self.compose("shijian", ["时间", "我们明天下午三点开会"])
        t = self.tr(cl.gen)
        self.assertEqual((t[1]["source"], t[2]["source"]), ("cache", "cache"))
        self.assertEqual(len(self.mock.posts()), 1)
        self.b.pipeline.cache.save()
        fresh = tcache.Cache(Dictionary().is_headword)
        fresh.open(str(self.dir))
        self.assertEqual(fresh.get("ja", "时间"), "Tja(时间)")
        self.assertIsNone(fresh.get("ja", "我们明天下午三点开会"))

    def test_errors_states_and_retry(self):
        self.mock.mode = "auth"
        cl = self.compose("shijian", ["试剑"])
        self.pump(2, self.settled(cl))
        self.assertEqual((cl.items[0].state, cl.items[0].reason), ("failed", "auth"))
        self.assertEqual(self.svc_state(), "auth")
        self.mock.mode = "ok"
        self.b.handle({"type": "retry", "gen": cl.gen, "n": 1})
        self.pump(2, self.settled(cl))
        self.assertEqual(cl.items[0].state, "done")
        self.assertEqual(self.svc_state(), "ok")
        self.mock.mode = "slow"
        cl = self.compose("x", ["慢词"])
        self.pump(4, self.settled(cl))
        self.assertEqual((cl.items[0].state, cl.items[0].reason), ("failed", "timeout"))
        self.assertEqual(self.svc_state(), "offline")

    def test_offline_unreachable(self):
        self.configure(services={"custom": {"protocol": "openai", "endpoint": "http://127.0.0.1:9/v1", "model": "m", "auth": "bearer"}})
        cl = self.compose("x", ["试剑"])
        self.pump(4, self.settled(cl))
        self.assertEqual(cl.items[0].reason, "network")
        self.assertEqual(self.svc_state(), "offline")

    def test_slow_request_is_hedged(self):
        from translate_backend.translate import pipeline
        with patch.object(pipeline, "HEDGE_S", 0.3):
            self.mock.delay = 1.5  # first request hangs; the hedge goes out 0.3 s after it was sent
            cl = self.compose("x", ["慢一点"])
            self.pump(1.0, lambda: len(self.mock.posts()) >= 1)
            self.mock.delay = 0.0  # the duplicate answers at once
            t0 = time.monotonic()
            self.pump(3, self.settled(cl))
        self.assertEqual(cl.items[0].state, "done")
        self.assertLess(time.monotonic() - t0, 1.2)  # did not wait for the hung original
        self.assertEqual(len(self.mock.posts()), 2)
        self.pump(1.5)  # the late original arrives and is ignored
        self.assertEqual(self.svc_state(), "ok")

    def test_local_only_and_no_key(self):
        self.configure(localOnly=True)
        cl = self.compose("x", ["时间", "试剑"])
        self.assertEqual([i.state for i in cl.items], ["done", "noEntry"])
        self.assertEqual(self.svc_state(), "localOnly")
        self.configure(localOnly=False, target="ko")
        cl = self.compose("y", ["时间"])
        self.pump(2, self.settled(cl))
        self.assertEqual(cl.items[0].text, "时间")
        self.assertEqual(cl.items[0].translation, "Tko(时间)")  # no dictionary for Korean: service
        self.b.handle({"type": "secret.set", "provider": "custom", "key": ""})
        cl = self.compose("z", ["试剑"])
        self.assertEqual((cl.items[0].state, self.svc_state()), ("noEntry", "noService"))
        self.assertEqual(len(self.mock.posts()), 1)

    def test_garbage_reply(self):
        self.mock.mode = "garbage"
        cl = self.compose("x", ["试剑"])
        self.pump(2, self.settled(cl))
        self.assertEqual((cl.items[0].state, cl.items[0].reason), ("failed", "parse"))

    def test_test_connection_and_models_all_formats(self):
        for proto, path in (("openai", "/v1"), ("anthropic", ""), ("gemini", "/v1beta")):
            svc = {"provider": "custom", "protocol": proto, "endpoint": self.mock.url + path, "model": "mock-a",
                   "auth": {"openai": "bearer", "anthropic": "x-api-key", "gemini": "x-goog-api-key"}[proto]}
            self.b.handle({"type": "service.test", "id": 1, "service": svc, "key": "typed"})
            self.b.handle({"type": "service.models", "id": 2, "service": svc})
            self.pump(1.0, lambda: len(self.msgs("service.models")) >= 1 and len(self.msgs("service.test")) >= 1)
            t, m = self.msgs("service.test")[-1], self.msgs("service.models")[-1]
            self.assertTrue(t["ok"], (proto, t))
            self.assertEqual(m["models"], ["mock-a", "mock-b"], proto)
            self.out.truncate(0), self.out.seek(0)
        self.mock.mode = "refuse"
        self.b.handle({"type": "service.test", "id": 3, "service": {"provider": "custom", "protocol": "anthropic", "endpoint": self.mock.url, "model": "m", "auth": "x-api-key"}, "key": "k"})
        self.pump(1.0, lambda: self.msgs("service.test"))
        self.assertEqual(self.msgs("service.test")[-1]["error"], "refused")
        self.b.handle({"type": "service.test", "id": 4, "service": {"provider": "custom", "endpoint": "ftp://x", "model": "m"}, "key": "k"})
        self.pump(0.5, lambda: len(self.msgs("service.test")) >= 2)
        self.assertEqual(self.msgs("service.test")[-1]["error"], "badUrl")

    def test_keys_never_in_output(self):
        cl = self.compose("x", ["试剑"])
        self.pump(2, self.settled(cl))
        self.b.handle({"type": "secret.status", "id": 5})
        out = self.out.getvalue().decode()
        self.assertNotIn("k-test", out)
        self.assertTrue(self.msgs("secret.status")[-1]["keys"]["custom"])


if __name__ == "__main__":
    unittest.main()
