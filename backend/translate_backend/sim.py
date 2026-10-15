"""Simulated input-method candidate source and translation provider.

Stands in for the WeChat IME adapter and the cloud/dictionary providers until they are integrated
(stage 3, steps 4–5). It produces exactly the events the real adapter will: candidate lists with a
generation, an anchor rectangle, and asynchronous per-item translation results.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

# Same sample data as the prototype (prototype/src/data/scenarios.ts), trimmed to what tests need.
LISTS: dict[str, list[tuple[str, dict[str, str]]]] = {
    "short": [
        ("时间", {"en": "time", "ja": "時間", "ko": "시간"}),
        ("事件", {"en": "event", "ja": "出来事", "ko": "사건"}),
        ("实践", {"en": "practice", "ja": "実践", "ko": "실천"}),
        ("世间", {"en": "the world", "ja": "世の中", "ko": "세상"}),
        ("试剑", {"en": "test a sword", "ja": "試し斬り", "ko": "칼을 시험하다"}),
    ],
    "sentence": [
        (
            "我们明天下午三点在会议室讨论这个问题请大家提前准备好上周的数据",
            {
                "en": "We'll discuss this in the meeting room at 3 p.m. tomorrow — please have last week's figures ready beforehand.",
                "ja": "明日の午後3時に会議室でこの件について話し合います。事前に先週のデータを準備しておいてください。",
                "ko": "내일 오후 3시에 회의실에서 이 문제를 논의하겠습니다. 미리 지난주 데이터를 준비해 주세요.",
            },
        ),
        ("我们明天下午三点", {"en": "We, at 3 p.m. tomorrow", "ja": "私たちは明日の午後3時に", "ko": "우리는 내일 오후 3시에"}),
        ("我们明天", {"en": "We, tomorrow", "ja": "私たちは明日", "ko": "우리는 내일"}),
        ("我们", {"en": "we", "ja": "私たち", "ko": "우리"}),
        ("我", {"en": "I", "ja": "私", "ko": "나"}),
    ],
    "unicode": [
        ("你好", {"en": "Hello — naïve café ✓ 😀", "ja": "こんにちは", "ko": "안녕하세요"}),
        ("谢谢", {"en": "Thanks", "ja": "ありがとう", "ko": "감사합니다"}),
        ("再见", {"en": "Goodbye", "ja": "さようなら", "ko": "안녕히 가세요"}),
    ],
}


@dataclass
class Candidate:
    n: int
    text: str
    translation: str | None = None
    state: str = "loading"  # loading | done | failed | noEntry
    source: str | None = None  # cache | dict | ai | sim
    reason: str | None = None  # why failed / noEntry (timeout, network, auth, noEntry, noEntryLang, …)


@dataclass
class CandidateList:
    gen: int
    pinyin: str
    items: list[Candidate]
    anchor: dict  # physical px rect of the (simulated) IME candidate window
    created: float = field(default_factory=time.monotonic)


class SimSource:
    """Emits candidate lists on demand (driven by the host's debug channel in test mode)."""

    def __init__(self, on_list, on_translation, on_end):
        self._gen = 0
        self._on_list = on_list
        self._on_translation = on_translation
        self._on_end = on_end
        self.current: CandidateList | None = None
        self._lock = threading.Lock()

    def compose(self, scenario: str, pinyin: str, anchor: dict, target: str, latency_ms: int = 120, count: int = 5) -> CandidateList:
        data = LISTS.get(scenario, LISTS["short"])[:count]
        with self._lock:
            self._gen += 1
            cl = CandidateList(self._gen, pinyin, [Candidate(i + 1, t) for i, (t, _) in enumerate(data)], anchor)
            self.current = cl
        self._on_list(cl)
        # Translations arrive asynchronously; obsolete generations are dropped on delivery.
        for i, (_, tr) in enumerate(data):
            delay = (latency_ms + 25 * i) / 1000
            timer = threading.Timer(delay, self._deliver, args=(cl.gen, i + 1, tr.get(target, tr["en"])))
            timer.daemon = True
            timer.start()
        return cl

    def _deliver(self, gen: int, n: int, text: str) -> None:
        with self._lock:
            cl = self.current
            if not cl or cl.gen != gen:
                return  # list changed; drop stale result
            item = cl.items[n - 1]
            item.translation, item.state = text, "done"
        self._on_translation(gen, item)

    def end(self) -> None:
        with self._lock:
            cl, self.current = self.current, None
        if cl:
            self._on_end(cl.gen)
