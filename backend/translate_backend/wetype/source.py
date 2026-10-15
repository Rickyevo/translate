"""In-memory WeType candidate source. No network calls or candidate-text logging."""
from __future__ import annotations

from pathlib import Path
import sys
import threading

from .. import win32
from ..log import log
from ..sim import Candidate, CandidateList
from .protocol import Framer, decode, ListEvent, CompositionEvent, CommitEvent


def _letters(pinyin: str) -> str:
    """The typed letters of a composition, without WeType's segmentation marks."""
    return "".join(c for c in pinyin.lower() if c not in "' ")


def denied(exe: str, names) -> bool:
    return exe.lower().removesuffix(".exe") in {
        str(name).strip().lower().removesuffix(".exe") for name in names}


class WeTypeSource:
    """State is mutated only by the backend dispatch thread; workers enqueue notifications.

    Generations: every distinct candidate list gets a new `gen`. A pinyin change invalidates the current
    list at once (inserts against it are refused as stale) but does *not* end the composition for the
    host: the panel keeps showing the previous list until the replacement arrives a few ms later, so it
    neither flickers nor loses its per-composition state on every keystroke. `composition.end` is sent
    only when the composition really ends (commit, clear/cancel, window hidden, focus change, pause).

    `replay=True` (test mode only) starts no Frida or window threads; the host feeds synthetic pipe bytes
    and window metadata through the same accept() path, and foreground checks use that metadata.
    """

    def __init__(self, on_list, on_translation, on_end, post, on_status, replay: bool = False):
        self._on_list, self._on_translation, self._on_end = on_list, on_translation, on_end
        self._post, self._on_status = post, on_status
        self.replay = replay
        self.current = None
        self.foreground = {}
        self.config = {"count": 5, "target": "en", "denylist": []}
        self.paused = False
        self.composing = False  # a pinyin composition is in progress (pipe) and its window is visible
        self.connection = "starting"
        self._gen = 0
        self._shown = None  # gen the host is displaying and has not been told has ended
        self._pinyin = ""
        self._words = []
        self._framers = {}
        self._window = None
        self._epoch = 0
        self._connected = False
        self._started = False
        self._needs_composition = True
        self._data_seen = False
        self._stats = {"lists": 0, "pinyin": 0, "dup": 0, "dropped": 0, "late": 0}
        self._stop = threading.Event()
        self._threads = []

    # ---- host-facing -------------------------------------------------------------------------
    def configure(self, config):
        changed = any(config.get(k) != self.config.get(k) for k in ("target", "count", "denylist"))
        self.config = dict(config)
        if changed:
            self.end()
            self._needs_composition = True
        if not self._started:
            self._started = True
            if self.replay:
                return
            for name, fn in (("wetype-transport", self._transport), ("wetype-window", self._watch_window)):
                th = threading.Thread(target=fn, name=name, daemon=True)
                self._threads.append(th)
                th.start()

    def close(self):
        self._stop.set()
        if getattr(self, "_watcher", None):
            self._watcher.stop()
        for th in self._threads:
            th.join(timeout=1.5)
        self.end()
        self._framers.clear()

    def end(self):
        """The composition ended (or must be treated as ended): drop the list and tell the host once."""
        self._invalidate()
        self._pinyin = ""
        shown, self._shown = self._shown, None
        if shown is not None:
            self._on_end(shown)
            s = self._stats
            # Counts only — used to verify the IME's event ordering on real input.
            log.info("composition end gen=%d lists=%d pinyin=%d dup=%d dropped=%d late=%d",
                     shown, s["lists"], s["pinyin"], s["dup"], s["dropped"], s["late"])
        self._stats = {"lists": 0, "pinyin": 0, "dup": 0, "dropped": 0, "late": 0}

    def _invalidate(self):
        self.current = None
        self._words = []

    def set_paused(self, paused):
        self.paused = paused
        self.end()
        self.composing = False
        self._framers.clear()
        self._needs_composition = True

    def composition_visible(self) -> bool:
        """The IME's candidate window is showing, so Esc will be consumed by the IME, not the app."""
        if self.replay:
            return self._window is not None
        return win32.wetype_candidate_rect() is not None

    def _fg_hwnd(self) -> int:
        if self.replay:
            return self.foreground.get("hwnd", 0)
        return int(win32.user32.GetForegroundWindow() or 0)

    def _fg_info(self) -> dict:
        return dict(self.foreground) if self.replay else win32.foreground()

    def _input_allowed(self):
        return (not self.paused and self.foreground.get("pid", 0) != 0
                and not self.foreground.get("password", False)
                and not denied(self.foreground.get("exe", ""), self.config.get("denylist", [])))

    def _allowed(self):
        return self._input_allowed() and self._window is not None

    def _reset(self):
        self.end()
        self.composing = False
        self._framers.clear()
        self._needs_composition = True

    def _publish(self, cl):
        """Show a list once the IME's candidate window is visible (it may appear after the pipe data)."""
        cl.anchor = dict(self._window)
        if self._gen_published_late(cl):
            self._stats["late"] += 1
        self._shown = cl.gen
        self._on_list(cl)

    def _gen_published_late(self, cl) -> bool:
        return getattr(cl, "_pending", False)

    def _probe_later(self):
        """Fallback if the window-shown notification is missed: re-check the window directly, shortly."""
        if self.replay:
            return
        for delay in (0.03, 0.1, 0.3):
            t = threading.Timer(delay, self._post, args=({"kind": "probe"},))
            t.daemon = True
            t.start()

    def check_target(self) -> str | None:
        """None if inserting into the composition's window is allowed now; else an insert error code."""
        fg = self._fg_info()
        expected = self.foreground
        if fg.get("password", False) or denied(fg.get("exe", ""), self.config.get("denylist", [])):
            return "denied"
        if (self.current is None or not self._allowed()
                or (fg.get("hwnd"), fg.get("pid")) != (expected.get("hwnd"), expected.get("pid"))):
            return "stale"
        return None

    def validate_target(self):
        return self.check_target() is None

    # ---- events --------------------------------------------------------------------------------
    def accept(self, event):
        """Consume a private event from the backend queue. Never forward raw pipe data."""
        kind = event["kind"]
        if kind == "connection":
            self._epoch = event["epoch"]
            self._connected = event["state"] == "connected"
            self.connection = event["state"]
            self._data_seen = False
            self.end()
            self.composing = False
            self._framers.clear()
            self._needs_composition = True
            self._on_status(event["state"], event.get("code"))
            return
        if kind == "window":
            fg, rect = event["foreground"], event["rect"]
            switched = (fg.get("hwnd"), fg.get("pid")) != (self.foreground.get("hwnd"), self.foreground.get("pid"))
            old_rect = self._window
            self.foreground, self._window = fg, rect
            if switched or not self._input_allowed():
                self._reset()
            elif rect is None:
                if self._shown is not None:  # the candidate window closed: the composition is over
                    self._reset()
            elif self.current and self._shown != self.current.gen:
                self._publish(self.current)  # list arrived before its window became visible
            elif rect != old_rect and self.current:
                self.current.anchor = rect
                self._on_list(self.current)  # same gen: a reposition, not a new list
            return
        if kind == "probe":
            if self.current and self._shown != self.current.gen and self._window is None:
                rect = win32.wetype_candidate_rect()
                if rect:
                    self._window = rect
                    self._publish(self.current)
            return
        if kind != "bytes" or event["epoch"] != self._epoch or not self._connected:
            return
        if not self._data_seen:
            self._data_seen = True
            log.info("ime data flowing (epoch %d)", self._epoch)
        # The cached foreground can lag a focus change by a few ms; refresh instead of dropping data.
        if self._fg_hwnd() != self.foreground.get("hwnd"):
            fg = self._fg_info()
            if self.foreground:
                self._reset()
            self.foreground = fg
        if not self._input_allowed():
            self._framers.clear()
            return
        handle = event["handle"]
        if handle not in self._framers and len(self._framers) >= 16:
            self._framers.clear()
        framer = self._framers.setdefault(handle, Framer())
        for message in framer.feed(event["data"]):
            self._decoded(decode(message))

    def _decoded(self, event):
        if isinstance(event, CompositionEvent):
            if not event.pinyin:
                self.end()
                self.composing = False
                self._needs_composition = True
            elif _letters(event.pinyin) == _letters(self._pinyin):
                # Same keystrokes, re-segmented ("shijian" → "shi'jian") or re-sent: WeType does this on its own,
                # without a new list. Not a keystroke — keep the list (live run: Alt+2 was refused as stale here).
                self._pinyin = event.pinyin
                self.composing = True
                self._needs_composition = False
            elif event.pinyin != self._pinyin:
                # Refuse inserts against the old list at once; the host keeps showing it until the
                # replacement arrives (no hide/show per keystroke).
                self._invalidate()
                self._pinyin = event.pinyin
                self.composing = True
                self._needs_composition = False
                self._stats["pinyin"] += 1
        elif isinstance(event, CommitEvent):
            self.end()
            self.composing = False
            self._needs_composition = True
        elif isinstance(event, ListEvent):
            if self._needs_composition:
                self._stats["dropped"] += 1  # a list without a composition we saw start
                return
            words = event.texts[:max(1, min(9, int(self.config.get("count", 5))))]
            if not words:
                self.end()
                return
            if self.current and words == self._words:
                self._stats["dup"] += 1
                return
            self._gen += 1
            self._words = words
            self._stats["lists"] += 1
            cl = CandidateList(self._gen, self._pinyin,
                               [Candidate(i + 1, text) for i, text in enumerate(words)], dict(self._window or {}))
            self.current = cl
            if self._window is not None:
                self._publish(cl)
            else:
                cl._pending = True  # shown when the candidate window appears
                self._probe_later()

    # ---- workers -------------------------------------------------------------------------------
    def _watch_window(self):
        """Event-driven (WinEvent hooks): wakes only when focus/foreground changes or the candidate window
        shows, hides or moves. Posts metadata only when it actually changed."""
        previous = [None]

        def sample():
            try:
                rect = win32.wetype_candidate_rect(watcher.target_hwnd or None)
                fg = win32.foreground()
                # Only metadata is inspected here; no text APIs or keyboard hooks.
                key = (rect, fg.get("hwnd"), fg.get("pid"), fg.get("focus"), fg.get("password", False))
                if key != previous[0]:
                    self._post({"kind": "window", "rect": rect, "foreground": fg})
                    previous[0] = key
            except Exception:
                self._post({"kind": "window", "rect": None, "foreground": {}})
                previous[0] = None

        watcher = win32.WindowEvents(win32.wetype_candidate_hwnd, sample)
        self._watcher = watcher
        watcher.run()

    def _transport(self):
        vendor = Path(__file__).resolve().parents[2] / "vendor"
        if vendor.is_dir() and str(vendor) not in sys.path:
            sys.path.insert(0, str(vendor))
        try:
            import frida
        except ImportError:
            self._post({"kind": "connection", "state": "failed", "epoch": 0, "code": "frida_missing"})
            return
        agent = Path(__file__).with_name("agent.js").read_text(encoding="utf-8")
        epoch = 0
        while not self._stop.is_set():
            epoch += 1
            session = None
            disconnected = threading.Event()
            try:
                # Attach only to the candidate-producing server, never the renderer.
                session = frida.attach("wetype_server.exe")
                session.on("detached", lambda *args: disconnected.set())
                script = session.create_script(agent)
                def message(msg, data, current_epoch=epoch):
                    if msg.get("type") == "send":
                        payload = msg.get("payload") or {}
                        if payload.get("t") == "w" and data:
                            self._post({"kind": "bytes", "epoch": current_epoch,
                                        "handle": payload["handle"], "data": data})
                        elif payload.get("t") == "disabled":
                            disconnected.set()
                    elif msg.get("type") == "error":
                        disconnected.set()
                script.on("message", message)
                # Epoch is published before callbacks can deliver bytes.
                self._post({"kind": "connection", "state": "connected", "epoch": epoch})
                script.load()
                while not self._stop.wait(0.25) and not disconnected.is_set():
                    pass
            except Exception as exc:
                # Exception messages can contain source data; send a classification only.
                code = type(exc).__name__
                self._post({"kind": "connection", "state": "waiting", "epoch": epoch, "code": code})
            finally:
                if session:
                    try:
                        session.detach()
                    except Exception:
                        pass
            if not self._stop.is_set():
                self._post({"kind": "connection", "state": "waiting", "epoch": epoch})
                self._stop.wait(3)
