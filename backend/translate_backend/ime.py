"""The input methods Translate follows: WeChat Input Method (WeType), Microsoft Pinyin, or both ("auto").

Each runs its own source (same state machine and host contract); this object routes their events by tag and
presents the one that is composing as *the* source to the backend. In "auto" both observers run, and whichever
input method opens a composition becomes active (the other's composition, if any, is ended). WeType's Frida runtime
is only loaded while WeType is selected or running (see WeTypeSource._transport), so Microsoft Pinyin users don't pay
for it.
"""
from __future__ import annotations

from .mspinyin.source import MsPinyinSource
from .wetype.source import WeTypeSource

MODES = {"auto": ("wetype", "mspinyin"), "wetype": ("wetype",), "mspinyin": ("mspinyin",)}


class ImeSources:
    def __init__(self, on_list, on_translation, on_end, post, on_status, replay: bool = False):
        self._handlers = (on_list, on_translation, on_end)
        self._post, self._on_status = post, on_status
        self.replay = replay
        self.mode = "auto"
        self.sources: dict = {}
        self.active = None
        self._status: dict[str, tuple] = {}
        self._genbox = [0]
        self._ensure(MODES["auto"])

    # ---- sources ------------------------------------------------------------------------------
    def _make(self, name):
        def post(ev, n=name):
            self._post({**ev, "ime": n})

        def status(state, code=None, n=name):
            self._status[n] = (state, code)
            self._report()

        cls = WeTypeSource if name == "wetype" else MsPinyinSource
        s = cls(*self._handlers, post, status, replay=self.replay)
        s._genbox = self._genbox  # one generation sequence across input methods
        return s

    def _ensure(self, names):
        for n in list(self.sources):
            if n not in names:
                s = self.sources.pop(n)
                if self.active is s:
                    s.end()
                    self.active = None
                s.close()
                self._status.pop(n, None)
        for n in names:
            if n not in self.sources:
                self.sources[n] = self._make(n)

    def _report(self):
        """One status for the host: the active input method's, else the best of the running ones."""
        order = {"connected": 0, "waiting": 1, "starting": 2, "failed": 3}
        if self.active is not None and self.active.name in self._status:
            name = self.active.name
        elif self._status:
            name = min(self._status, key=lambda n: order.get(self._status[n][0], 9))
        else:
            return
        state, code = self._status[name]
        self._on_status(state, code, name, {n: s[0] for n, s in self._status.items()})

    @property
    def _primary(self):
        return self.active or self.sources.get("wetype") or next(iter(self.sources.values()))

    # ---- backend-facing (the same surface as one source) ---------------------------------------
    def configure(self, config):
        mode = config.get("ime", "auto")
        self.mode = mode if mode in MODES else "auto"
        self._ensure(MODES[self.mode])
        for s in self.sources.values():
            s.configure(config)
        self._report()

    def accept(self, event):
        name = event.get("ime", "wetype")
        s = self.sources.get(name)
        if s is None:
            return
        s.accept(event)
        if s.composing and self.active is not s:
            if self.active is not None and self.active.composing:
                self.active.end()  # the other input method took over
                self.active.composing = False
            self.active = s
            self._report()
        elif self.active is None and s.current is not None:
            self.active = s

    def end(self):
        for s in self.sources.values():
            s.end()

    def set_paused(self, paused):
        for s in self.sources.values():
            s.set_paused(paused)

    def close(self):
        for s in self.sources.values():
            s.close()

    @property
    def config(self):  # the active input method's (all get the same configure())
        return self._primary.config

    @property
    def current(self):
        return self._primary.current

    @property
    def foreground(self):
        return self._primary.foreground

    @property
    def composing(self):
        return self._primary.composing

    @property
    def connection(self):
        return self._primary.connection

    @property
    def _epoch(self):  # replay tests feed WeType pipe bytes with its epoch
        return self.sources["wetype"]._epoch if "wetype" in self.sources else 0

    def composition_visible(self):
        return self._primary.composition_visible()

    def check_target(self):
        return self._primary.check_target()

    def validate_target(self):
        return self._primary.validate_target()

    def _fg_info(self):
        return self._primary._fg_info()
