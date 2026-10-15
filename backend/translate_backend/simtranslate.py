"""Simulated translation provider for real candidates (stage 4). No network, no disk, no logging of text.

Every result is visibly marked "[sim]" so it can never be mistaken for a real translation, in the panel or
after insertion. Known words from the sample data get their sample translation; anything else echoes the
candidate. Results arrive asynchronously with a small per-item latency, like a real provider, so stale-result
rejection is exercised on every keystroke.
"""
from __future__ import annotations

import heapq
import itertools
import threading
import time

from .sim import LISTS

MARK = "[sim] "
_DICT: dict[str, dict[str, str]] = {text: tr for rows in LISTS.values() for text, tr in rows}


def simulate(text: str, target: str) -> str:
    tr = _DICT.get(text)
    return MARK + (tr.get(target, tr["en"]) if tr else text)


class Scheduler:
    """One thread for every delayed event (translations, timeouts) instead of one timer thread each.
    Sleeps until the next due item; ≈0 % CPU when empty."""

    def __init__(self, post):
        self._post = post
        self._heap: list = []
        self._seq = itertools.count()
        self._cv = threading.Condition()
        self._closed = False
        threading.Thread(target=self._run, name="scheduler", daemon=True).start()

    def at(self, delay_s: float, event: dict) -> None:
        with self._cv:
            heapq.heappush(self._heap, (time.monotonic() + delay_s, next(self._seq), event))
            self._cv.notify()

    def close(self) -> None:
        with self._cv:
            self._closed = True
            self._cv.notify()

    def _run(self) -> None:
        while True:
            with self._cv:
                while not self._closed and (not self._heap or self._heap[0][0] > time.monotonic()):
                    self._cv.wait(None if not self._heap else max(0.0, self._heap[0][0] - time.monotonic()))
                if self._closed:
                    return
                _, _, event = heapq.heappop(self._heap)
            self._post(event)


class SimTranslator:
    """Schedules one `_translation` event per item; the dispatch thread applies it only if `gen` is current."""

    def __init__(self, scheduler: Scheduler, latency_ms: int = 60, step_ms: int = 20):
        self._sched = scheduler
        self.latency_ms, self.step_ms = latency_ms, step_ms

    def request(self, gen: int, items, target: str) -> None:
        for i, item in enumerate(items):
            self._sched.at((self.latency_ms + self.step_ms * i) / 1000,
                           {"type": "_translation", "gen": gen, "n": item.n, "text": simulate(item.text, target)})
