"""Translate backend entry point: `python -m translate_backend [--test [--source=wetype-replay]]`.

Single dispatch loop on the main thread; the stdin reader, the IME adapter's workers and the scheduler feed
it through a queue, so all state changes happen in one place and the process sleeps (≈0 % CPU) when nothing
is happening.

Sources:
  (default)                       WeTypeSource, live: native observer on wetype_server + window metadata
  --test                          SimSource: scripted lists with fixture translations (stage-3 harness)
  --test --source=wetype-replay   WeTypeSource fed synthetic pipe bytes by the host (debug.wetype.*)
Translations: live mode uses the real pipeline (translate/: cache → CC-CEDICT → the configured service). The replay
source keeps the marked "[sim]" translator (simtranslate.py) unless --translator=live is given.
"""
from __future__ import annotations

import base64
import collections
import os
import queue
import sys
import threading
import time

from . import win32
from .log import log
from .protocol import PROTOCOL_VERSION, read_messages, reply, send
from .sim import SimSource
from .simtranslate import Scheduler, SimTranslator
from .translate import providers as tproviders, secrets as tsecrets
from .translate.pipeline import Pipeline
from .wetype import encode
from .wetype.source import WeTypeSource
from .ime import ImeSources
from .mspinyin.source import MsPinyinSource

VERSION = "0.2.4"
COMPOSITION_CANCEL_TIMEOUT = 0.5  # s to wait for the IME to confirm Esc cancelled the composition
SETTLE_AFTER_CANCEL = 0.015       # s between the confirmed cancel and typing (lets the IME's text service settle)


class RealInput:
    send_key = staticmethod(win32.send_key)
    send_unicode = staticmethod(win32.send_unicode)
    modifiers_down = staticmethod(win32.modifiers_down)


class DryInput:
    """Test-mode stand-in for SendInput: records what would be typed and emulates the IME's reaction to Esc
    ("clear": composition cleared on the pipe, "hide": candidate window hidden, "none": IME ignores it)."""

    def __init__(self, backend: "Backend"):
        self.b = backend
        self.log: list[dict] = []
        self.on_escape = "clear"
        self.held: list[str] = []

    def send_key(self, vk: int) -> int:
        self.log.append({"key": vk})
        src = self.b.source
        active = src._primary if isinstance(src, ImeSources) else src
        if vk == win32.VK_ESCAPE and isinstance(active, MsPinyinSource):
            if self.on_escape in ("clear", "hide"):  # Microsoft Pinyin: Esc closes its candidate window
                self.b.events.put({"type": "_source", "event": {"kind": "mspy", "ime": "mspinyin", "texts": [], "rect": None, "foreground": dict(active.foreground)}})
        elif vk == win32.VK_ESCAPE and isinstance(active, WeTypeSource):
            if self.on_escape == "clear":
                self.b.events.put({"type": "_source", "event": {"kind": "bytes", "epoch": src._epoch, "handle": "replay", "data": encode.composition("")}})
            elif self.on_escape == "hide":
                self.b.events.put({"type": "_source", "event": {"kind": "window", "rect": None, "foreground": dict(src.foreground)}})
        return 2

    def send_unicode(self, text: str) -> int:
        self.log.append({"text": text})
        return len(text.encode("utf-16-le"))

    def modifiers_down(self) -> list[str]:
        return list(self.held)


class Backend:
    def __init__(self, test_mode: bool, source: str = ""):
        self.test_mode = test_mode
        self.events: queue.Queue = queue.Queue()
        self._backlog: collections.deque = collections.deque()  # messages deferred while an insert waits
        self.paused = False
        self.config: dict = {"target": "en", "count": 5, "denylist": [], "localOnly": False}
        self.replay = test_mode and source in ("wetype-replay", "mspy-replay")
        self.input = DryInput(self) if self.replay else RealInput()
        self.scheduler = None
        self.translator = None
        self.pipeline = None
        self.stale_results = 0
        self._requested_gen = 0
        if test_mode and not self.replay:
            self.source = SimSource(self._emit_list, self._emit_translation, self._emit_end)
        else:
            self.source = ImeSources(self._emit_list, self._emit_translation, self._emit_end,
                                     self._post_source, self._ime_status, replay=self.replay)
            self.scheduler = Scheduler(self.events.put)
            if self.replay and "--translator=live" not in sys.argv:
                self.translator = SimTranslator(self.scheduler)
            else:
                self.pipeline = Pipeline(self.scheduler, self.events.put, self._deliver, self._service_state,
                                         lambda: self.source.current)
        self.running = True

    @property
    def live(self) -> bool:
        return isinstance(self.source, ImeSources)

    def _post_source(self, event):
        self.events.put({"type": "_source", "event": event})

    @property
    def translation_mode(self) -> str:
        return "live" if self.pipeline else "simulated" if self.translator else "fixture"

    def _ime_status(self, state, code=None, name=None, all_states=None):
        send("status", ime={"state": state, "code": code, "name": name, "all": all_states or {}}, translationMode=self.translation_mode)

    def _service_state(self, state: str) -> None:
        send("status", service={"state": state})

    def _deliver(self, gen: int, n: int, state: str, text, source, reason=None) -> None:
        cl = self.source.current
        if not cl or cl.gen != gen or not (0 < n <= len(cl.items)):
            self.stale_results += 1
            return
        item = cl.items[n - 1]
        item.state, item.translation, item.source, item.reason = state, text, source, reason
        send("translation", gen=gen, n=n, state=state, text=text, source=source, reason=reason)

    # ---- outbound ------------------------------------------------------------------------
    def _emit_list(self, cl) -> None:
        fg = self.source.foreground if self.live else win32.foreground()
        send(
            "candidates",
            gen=cl.gen,
            pinyin=cl.pinyin,
            items=[{"n": c.n, "text": c.text, "state": c.state} for c in cl.items],
            anchor=cl.anchor,
            foreground={"pid": fg.get("pid", 0), "exe": fg.get("exe", "")},
        )
        if cl.gen > self._requested_gen and (self.translator or self.pipeline):  # repositions re-send the same gen
            self._requested_gen = cl.gen
            (self.pipeline or self.translator).request(cl.gen, cl.items, self.config.get("target", "en"))
        log.debug("list gen=%d items=%d", cl.gen, len(cl.items))

    def _emit_translation(self, gen: int, item) -> None:
        send("translation", gen=gen, n=item.n, state=item.state, text=item.translation,
             source="sim" if self.live else None, simulated=True)

    def _emit_end(self, gen: int) -> None:
        send("composition.end", gen=gen)

    def _translation(self, ev: dict) -> None:
        cl = self.source.current
        if not cl or cl.gen != ev["gen"]:
            self.stale_results += 1  # list changed or ended: drop the stale result
            return
        item = cl.items[ev["n"] - 1]
        item.translation, item.state = ev["text"], "done"
        self._emit_translation(cl.gen, item)

    # ---- inbound -------------------------------------------------------------------------
    def handle(self, msg: dict) -> None:
        t = msg["type"]
        if t == "config.set":
            self.config.update(msg.get("config") or {})
            if self.live:
                self.source.configure(self.config)
            if self.pipeline:
                self.pipeline.configure(self.config)
            reply(msg, "config.ack", config=self.config)
        elif t == "secret.set":
            ok = tsecrets.set_key(str(msg.get("provider", "")), str(msg.get("key", "")))
            if self.pipeline:
                self.pipeline.key_changed()
            reply(msg, "secret.ack", ok=ok, provider=msg.get("provider"))
        elif t == "secret.status":
            reply(msg, "secret.status", keys={p: tsecrets.has_key(p) for p in tproviders.PRESETS})
        elif t in ("service.test", "service.models"):
            self._service_call(msg)
        elif t == "cache.stats":
            reply(msg, "cache.stats", **self._cache_stats())
        elif t == "cache.clear":
            if self.pipeline:
                self.pipeline.cache.clear()
            reply(msg, "cache.stats", **self._cache_stats())
        elif t == "retry":
            self._retry(msg)
        elif t == "pause":
            self.paused = True
            if self.live:
                self.source.set_paused(True)
            else:
                self.source.end()
            reply(msg, "status", paused=True)
        elif t == "resume":
            self.paused = False
            if self.live:
                self.source.set_paused(False)
            reply(msg, "status", paused=False)
        elif t == "insert":
            self._insert(msg)
        elif t == "composition.cancel":
            self.source.end()
        elif t == "ping":
            reply(msg, "pong", t=time.time())
        elif t == "shutdown":
            reply(msg, "bye")
            self.running = False
        elif t.startswith("debug.") and self.test_mode:
            self._debug(msg)
        else:
            reply(msg, "error", code="unknown_type", message=f"Unknown message type: {t}")

    def _cache_stats(self) -> dict:
        return self.pipeline.cache.stats() if self.pipeline else {"count": 0, "bytes": 0, "memory": 0}

    def _service_call(self, msg: dict) -> None:
        """Connection test / model list from the settings window, with the draft settings (not yet saved). Runs on its
        own thread: a slow service must not stall candidate handling. A key typed into the draft is used for this
        call only; otherwise the stored key."""
        svc = tproviders.resolve(msg.get("service") or {})
        svc["jsonMode"] = (msg.get("service") or {}).get("jsonMode", self.config.get("jsonMode", True))
        key = str(msg.get("key") or "") or tsecrets.get_key(svc["provider"])
        timeout = float(self.config.get("timeout", 8) or 8)
        target = self.config.get("target", "en")

        def run():
            if msg["type"] == "service.test":
                reply(msg, "service.test", **tproviders.test(svc, key, target, timeout))
                return
            try:
                reply(msg, "service.models", ok=True, models=tproviders.models(svc, key, timeout))
            except tproviders.HttpError as e:
                reply(msg, "service.models", ok=False, error=e.kind, status=e.status, detail=e.detail)
            except Exception as e:  # noqa: BLE001
                reply(msg, "service.models", ok=False, error="internal", status=0)
                log.error("models failed: %s", type(e).__name__)

        threading.Thread(target=run, name="service-call", daemon=True).start()

    def _retry(self, msg: dict) -> None:
        cl = self.source.current
        gen, n = msg.get("gen"), msg.get("n")
        if not self.pipeline or not cl or cl.gen != gen or not isinstance(n, int) or not (0 < n <= len(cl.items)):
            return
        item = cl.items[n - 1]
        if item.state in ("failed", "noEntry"):
            self._deliver(gen, n, "loading", None, None)
            self.pipeline.retry(gen, n, item.text, self.config.get("target", "en"))

    def _insert(self, msg: dict) -> None:
        cl = self.source.current
        gen, n = msg.get("gen"), msg.get("n")
        t0 = time.perf_counter()

        def done(ok: bool, error: str | None = None, exe: str | None = None):
            reply(msg, "insert.result", ok=ok, gen=gen, n=n, error=error, **({"target": {"exe": exe}} if exe is not None else {}))
            log.info("insert gen=%s n=%s ok=%s error=%s ms=%.0f", gen, n, ok, error, (time.perf_counter() - t0) * 1000)

        if not cl or cl.gen != gen:
            return done(False, "stale")
        item = cl.items[n - 1] if isinstance(n, int) and 0 < n <= len(cl.items) else None
        if not item or item.state != "done" or not item.translation:
            return done(False, "unavailable")
        text = item.translation
        if self.live:
            err = self.source.check_target()
            if err:
                return done(False, err)
            exe = self.source.foreground.get("exe", "")
        else:
            exe = win32.foreground()["exe"]
            if exe.lower() in {d.lower() for d in self.config.get("denylist", [])}:
                return done(False, "denied")
        # A hotkey leaves Alt held; typing now would be read as accelerators (and Esc as Alt+Esc). Tap an
        # unassigned key so the eventual Alt-up isn't a lone tap that opens the app's menu, then wait ≤ 1 s.
        if "alt" in self.input.modifiers_down():
            self.input.send_key(0xE8)
        deadline = time.monotonic() + 1.0
        while self.input.modifiers_down() and time.monotonic() < deadline:
            time.sleep(0.01)
        if self.input.modifiers_down():
            return done(False, "modifiers")
        if self.live:
            # Cancel the IME's pinyin composition before typing, else the pinyin (or a candidate) would be
            # left in the field. Esc is only sent while the candidate window is up, so it goes to the IME.
            if self.source.composing and self.source.composition_visible():
                self.input.send_key(win32.VK_ESCAPE)
                if not self._wait(lambda: not self.source.composing, COMPOSITION_CANCEL_TIMEOUT):
                    return done(False, "ime")
                time.sleep(SETTLE_AFTER_CANCEL)
            self.source.end()
            # The pump above may have processed a focus change.
            fg = self.source._fg_info()
            if (fg.get("hwnd"), fg.get("pid")) != (self.source.foreground.get("hwnd"), self.source.foreground.get("pid")):
                return done(False, "stale")
        else:
            self.source.end()
        sent = self.input.send_unicode(text)
        expected = len(text.encode("utf-16-le"))  # 2 events per UTF-16 unit
        ok = sent >= expected
        done(ok, None if ok else "blocked", exe)

    def _wait(self, pred, timeout: float) -> bool:
        """Process IME events (only) until pred() holds or the timeout passes. Other messages are deferred
        in order and handled right after the current one, so the dispatch loop stays single-threaded."""
        deadline = time.monotonic() + timeout
        while not pred():
            left = deadline - time.monotonic()
            if left <= 0:
                break
            try:
                m = self.events.get(timeout=left)
            except queue.Empty:
                break
            if m is not None and m.get("type") == "_source":
                self.source.accept(m["event"])
            elif m is not None and m.get("type") == "_translation":
                self._translation(m)
            elif m is not None and m.get("type") in ("_svc_flush", "_svc_result", "_svc_hedge", "_cache_save"):
                self.pipeline.accept(m)
            else:
                self._backlog.append(m)
        return pred()

    def _debug(self, msg: dict) -> None:
        t = msg["type"]
        if t.startswith(("debug.wetype.", "debug.mspy.")) or t == "debug.input":
            return self._debug_replay(msg)
        if self.live:
            return reply(msg, "error", code="unknown_type", message=f"Not available with this source: {t}")
        if t == "debug.compose" and not self.paused:
            self.source.compose(
                msg.get("scenario", "short"),
                msg.get("pinyin", "shi'jian"),
                msg.get("anchor") or {"x": 400, "y": 400, "w": 470, "h": 52},
                self.config.get("target", "en"),
                int(msg.get("latency", 120)),
                int(self.config.get("count", 5)),
            )
            reply(msg, "debug.ack")
        elif t == "debug.end":
            self.source.end()
            reply(msg, "debug.ack")
        elif t == "debug.typing":
            self._typing(msg)
            reply(msg, "debug.ack")
        elif t == "debug.foreground":
            reply(msg, "debug.foreground", **win32.foreground())

    def _debug_replay(self, msg: dict) -> None:
        """Replay source control: the same events the candidate transport and window watcher post."""
        if not self.replay:
            return reply(msg, "error", code="unknown_type", message="Replay source not active")
        t, src = msg["type"], self.source
        if t == "debug.wetype.connection":
            src.accept({"kind": "connection", "state": msg.get("state", "connected"), "epoch": int(msg.get("epoch", src._epoch + 1)), "code": msg.get("code")})
        elif t == "debug.wetype.window":
            fg = msg.get("foreground") or src.foreground or {"hwnd": 1, "pid": 4242, "exe": "replay-target.exe"}
            src.accept({"kind": "window", "rect": msg.get("rect"), "foreground": fg})
        elif t == "debug.wetype.bytes":
            data = base64.b64decode(msg["b64"]) if "b64" in msg else encode.build(msg.get("steps") or [])
            chunk = max(1, int(msg.get("chunk", len(data) or 1)))
            for i in range(0, len(data), chunk):
                src.accept({"kind": "bytes", "epoch": int(msg.get("epoch", src._epoch)), "handle": msg.get("handle", "replay"), "data": data[i:i + chunk]})
        elif t == "debug.mspy.connection":
            src.accept({"kind": "connection", "ime": "mspinyin", "state": msg.get("state", "connected"), "epoch": 1, "code": msg.get("code")})
        elif t == "debug.mspy.list":
            # What the UI Automation observer posts: Microsoft Pinyin's candidates and its window.
            fg = msg.get("foreground") or src.foreground or {"hwnd": 1, "pid": 4242, "exe": "replay-target.exe"}
            src.accept({"kind": "mspy", "ime": "mspinyin", "texts": list(msg.get("texts") or []), "rect": msg.get("rect"),
                        "canvas": msg.get("canvas"), "foreground": fg})
        elif t == "debug.mspy.close":
            src.accept({"kind": "mspy", "ime": "mspinyin", "texts": [], "rect": None, "foreground": src.foreground})
        elif t == "debug.wetype.typing":
            self._replay_typing(msg)
        elif t == "debug.input":
            inp = self.input
            if "onEscape" in msg:
                inp.on_escape = msg["onEscape"]
            if "held" in msg:
                inp.held = list(msg["held"])
            out = {"log": list(inp.log)}
            if msg.get("clear"):
                inp.log.clear()
            return reply(msg, "debug.input", **out)
        cl = src.current
        reply(msg, "debug.ack", gen=cl.gen if cl else None, composing=src.composing, connection=src.connection,
              staleResults=self.stale_results)

    def _replay_typing(self, msg: dict) -> None:
        """Continuous typing through the real adapter path: per keystroke a pinyin update + a new list,
        the candidate window moving right, a commit every few keystrokes (same cadence as debug.typing)."""
        interval = int(msg.get("interval", 150)) / 1000
        duration = float(msg.get("duration", 60))
        base = msg.get("rect") or {"x": 40, "y": 600, "w": 470, "h": 46}
        fg = msg.get("foreground") or {"hwnd": 1, "pid": 4242, "exe": "replay-target.exe"}
        words = ["时间", "事件", "实践", "世间", "试剑", "我们明天下午三点在会议室讨论这个问题请大家提前准备好上周的数据", "我们", "我"]
        post = self._post_source

        def run():
            end = time.monotonic() + duration
            k = 0
            while time.monotonic() < end and self.running:
                k += 1
                step = k % 7
                if step == 0:
                    post({"kind": "bytes", "epoch": self.source._epoch, "handle": "replay", "data": encode.commit()})
                    post({"kind": "window", "rect": None, "foreground": fg})
                else:
                    rect = {**base, "x": base["x"] + step * 9}
                    post({"kind": "window", "rect": rect, "foreground": fg})
                    lst = [words[(k + i) % len(words)] for i in range(6)]
                    post({"kind": "bytes", "epoch": self.source._epoch, "handle": "replay",
                          "data": encode.composition("py" * step) + encode.candidates(lst)})
                time.sleep(interval)
            post({"kind": "bytes", "epoch": self.source._epoch, "handle": "replay", "data": encode.commit()})
            post({"kind": "window", "rect": None, "foreground": fg})

        threading.Thread(target=run, name="replay-typing", daemon=True).start()

    def _typing(self, msg: dict) -> None:
        """Simulate continuous typing: a new candidate list every interval, the caret moving right,
        a composition ending every few keystrokes — the event pattern the real IME adapter produces."""
        interval = int(msg.get("interval", 150)) / 1000
        duration = float(msg.get("duration", 60))
        base = msg.get("anchor") or {"x": 40, "y": 600, "w": 470, "h": 52}
        scenarios = msg.get("scenarios") or ["short", "short", "sentence"]

        def run():
            end = time.monotonic() + duration
            k = 0
            while time.monotonic() < end and self.running:
                k += 1
                anchor = {**base, "x": base["x"] + (k % 12) * 9}
                if k % 7 == 0:
                    self.source.end()  # composition committed; next keystroke starts a new one
                elif not self.paused:
                    self.source.compose(scenarios[k % len(scenarios)], "py" + str(k % 50), anchor, self.config.get("target", "en"), 90, int(self.config.get("count", 5)))
                time.sleep(interval)
            self.source.end()

        threading.Thread(target=run, name="sim-typing", daemon=True).start()

    # ---- loop ----------------------------------------------------------------------------
    def run(self) -> int:
        def pump():
            for m in read_messages():
                self.events.put(m)
            self.events.put(None)  # stdin closed: host is gone

        mode = self.translation_mode
        send("ready", version=VERSION, protocol=PROTOCOL_VERSION, pid=os.getpid(), dpiAware=win32.enable_dpi_awareness(),
             testMode=self.test_mode, adapters=(["replay"] if self.replay else ["wetype", "mspinyin"]) if self.live else ["sim"],
             translationMode=mode)
        threading.Thread(target=pump, name="stdin", daemon=True).start()
        while self.running:
            msg = self._backlog.popleft() if self._backlog else self.events.get()
            if msg is None:
                log.info("host closed stdin; exiting")
                break
            try:
                kind = msg.get("type")
                if kind == "_source":
                    self.source.accept(msg["event"])
                elif kind == "_translation":
                    self._translation(msg)
                elif kind in ("_svc_flush", "_svc_result", "_svc_hedge", "_cache_save"):
                    self.pipeline.accept(msg)
                else:
                    self.handle(msg)
            except Exception as e:  # noqa: BLE001 — one bad message must not kill the backend
                log.error("handler failed: %s", type(e).__name__)
                reply(msg, "error", code="internal", message="The translation engine hit an internal error")
        if self.live:
            self.source.close()
        if self.pipeline:
            self.pipeline.close()
        if self.scheduler:
            self.scheduler.close()
        return 0


def _quiet_excepthooks() -> None:
    """Tracebacks can carry candidate text in exception messages or locals; log the type only."""
    sys.excepthook = lambda t, e, tb: log.error("uncaught %s", t.__name__)
    threading.excepthook = lambda a: log.error("thread %s failed: %s", a.thread.name if a.thread else "?", a.exc_type.__name__)


def main() -> int:
    _quiet_excepthooks()
    source = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--source=")), "")
    code = Backend(test_mode="--test" in sys.argv, source=source).run()
    # Exit without interpreter finalization: the stdin reader thread may still be blocked in read(),
    # and finalizing while it holds the buffer lock crashes CPython on Windows.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)


if __name__ == "__main__":
    sys.exit(main())
