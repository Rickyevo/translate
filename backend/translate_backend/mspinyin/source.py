"""Microsoft Pinyin candidate source. Same state machine and host contract as the WeType source (generations,
publishing, foreground and permission checks, insertion), fed by the UI Automation observer instead of pipe bytes.

Differences from WeType: the observer reports whole snapshots of the candidate window (its candidates and the bar's
rectangle), so a changed list is a new generation and an empty one means the window closed (the composition ended).
Microsoft Pinyin shows the pinyin inside the app, not in its window, so lists carry no pinyin.
"""
from __future__ import annotations

import threading

from .. import win32
from ..sim import Candidate, CandidateList
from ..wetype.source import WeTypeSource
from .observer import Observer


class MsPinyinSource(WeTypeSource):
    name = "mspinyin"

    def configure(self, config):
        changed = any(config.get(k) != self.config.get(k) for k in ("target", "count", "denylist"))
        self.config = dict(config)
        if changed:
            self.end()
        if not self._started:
            self._started = True
            if self.replay:
                return
            for name, fn in (("mspinyin-uia", Observer(self._post, self._stop).run), ("mspinyin-focus", self._watch_focus)):
                th = threading.Thread(target=fn, name=name, daemon=True)
                self._threads.append(th)
                th.start()

    def composition_visible(self) -> bool:
        """Microsoft Pinyin's candidate window is showing (so Esc goes to the input method, not the app)."""
        return self._window is not None

    def _watch_focus(self):
        """Foreground/focus changes (WinEvent hooks), so a composition in another window ends at once."""
        previous = [None]

        def sample():
            try:
                fg = win32.foreground()
                key = (fg.get("hwnd"), fg.get("pid"), fg.get("focus"), fg.get("password", False))
                if key != previous[0]:
                    previous[0] = key
                    self._post({"kind": "fg", "foreground": fg})
            except Exception:  # noqa: BLE001
                previous[0] = None

        watcher = win32.WindowEvents(lambda: 0, sample)
        self._watcher = watcher
        watcher.run()

    # ---- events --------------------------------------------------------------------------------
    def accept(self, event):
        kind = event["kind"]
        if kind == "fg":
            fg = event["foreground"]
            switched = (fg.get("hwnd"), fg.get("pid")) != (self.foreground.get("hwnd"), self.foreground.get("pid"))
            self.foreground = fg
            if switched or not self._input_allowed():
                self._window = None
                self._reset()
            return
        if kind == "mspy":
            return self._snapshot(event)
        if kind in ("connection",):
            return super().accept(event)

    def _snapshot(self, ev):
        if not self._connected:
            return
        if not self._data_seen:
            self._data_seen = True
        fg = ev.get("foreground") or self._fg_info()
        if (fg.get("hwnd"), fg.get("pid")) != (self.foreground.get("hwnd"), self.foreground.get("pid")) and self.foreground:
            self._reset()
        self.foreground = fg
        texts = [t for t in (ev.get("texts") or []) if t]
        if not texts or not self._input_allowed():
            # The candidate window closed (composition committed, cancelled, or moved elsewhere).
            self._window = None
            self.end()
            self.composing = False
            self._needs_composition = True
            return
        window = {**ev["rect"], "canvas": ev.get("canvas") or ev["rect"], "measured": True}
        if fg.get("caret"):
            window["caret"] = fg["caret"]
        old, self._window = self._window, window
        self.composing = True
        self._needs_composition = False
        words = texts[:max(1, min(9, int(self.config.get("count", 5))))]
        if self.current and words == self._words:
            if window != old:  # same list, the window moved
                self.current.anchor = dict(window)
                self._on_list(self.current)
            return
        self._invalidate()
        self._gen += 1
        self._words = words
        self._stats["lists"] += 1
        cl = CandidateList(self._gen, "", [Candidate(i + 1, t) for i, t in enumerate(words)], dict(window))
        self.current = cl
        self._publish(cl)
