"""Translation pipeline: cache → local dictionary → translation service, one batch per candidate list.

Runs on the backend dispatch thread except the HTTP calls, which run on two worker threads and post their results
back as `_svc_result` events. While typing, a service call is made only after the list has been stable for
DEBOUNCE_MS (each keystroke replaces the list), and jobs for lists that were replaced before a worker picked them
up are dropped, so fast typing costs one request per pause, not one per keystroke. Results of a finished request
are cached even if their list is gone, and any current row with the same text is filled from them.

Service state (reported to the host for the panel footer): ok · noService (no key/model) · localOnly · offline
(network) · auth (key rejected) · failed (other errors: rate limit, HTTP error, unreadable reply).
"""
from __future__ import annotations

import queue
import threading
import time

from ..log import log
from . import providers, secrets
from .errors import HttpError
from .cache import Cache
from .dictionary import Dictionary

HEDGE_S = 3.0  # no answer after this long (p95 ≈ 2.2 s): send the same request again, first answer wins
DEBOUNCE_MS = 250  # > the usual gap between pinyin keystrokes (≈ 120–200 ms): one request per pause, not per key


class Pipeline:
    def __init__(self, scheduler, post, deliver, on_service_state, current):
        self._sched, self._post, self._deliver = scheduler, post, deliver
        self._on_state, self._current = on_service_state, current
        self.dictionary = Dictionary()
        self.cache = Cache(self.dictionary.is_headword)
        self.config: dict = {}
        self.svc: dict = providers.resolve({"provider": "openai"})
        self.state = ""
        self._has_key = False  # refreshed on configure / key change, not read from the vault per keystroke
        self._latest = 0  # newest gen a job was requested for (read by workers)
        self._warm_sent = False  # reset when a service result arrives (connection known warm) or after idle
        self._pending: dict[int, dict[int, str]] = {}  # gen → {n: text} waiting for the debounce
        self._inflight: dict[str, set[str]] = {}  # target → texts being translated right now
        self._jobs: queue.Queue = queue.Queue()
        self._save_due = False
        self._job_id = 0
        self._open: dict[int, int] = {}  # job id → copies still running (1, or 2 once hedged)
        for i in range(3):  # 2 for requests + 1 spare so a hedge never waits behind them
            threading.Thread(target=self._worker, name=f"translate-{i}", daemon=True).start()

    # ---- configuration -----------------------------------------------------------------------
    def configure(self, config: dict) -> None:
        self.config = config
        services = config.get("services") or {}
        pid = config.get("provider") or "openai"
        self.svc = providers.resolve({**(services.get(pid) or {}), "provider": pid})
        self.svc["jsonMode"] = config.get("jsonMode", True)
        if config.get("dataDir"):
            self.cache.open(config["dataDir"])
        self._has_key = secrets.has_key(self.svc["provider"])
        self._set_state(self._baseline_state())

    def _baseline_state(self) -> str:
        if self.config.get("localOnly"):
            return "localOnly"
        if not self.svc.get("endpoint") or not self.svc.get("model"):
            return "noService"
        if providers.needs_key(self.svc) and not self._has_key:
            return "noService"
        return "ok" if self.state in ("", "noService", "localOnly") else self.state

    def _set_state(self, state: str) -> None:
        if state != self.state:
            self.state = state
            self._on_state(state)

    def key_changed(self) -> None:
        self._has_key = secrets.has_key(self.svc["provider"])
        self.state = ""
        self._set_state(self._baseline_state())

    # ---- per list ----------------------------------------------------------------------------
    def request(self, gen: int, items, target: str) -> None:
        self._latest = gen
        waiting: dict[int, str] = {}
        provisional: dict[int, str] = {}  # dictionary hits the service will refine (same request, no extra one)
        for it in items:
            hit = self.cache.get(target, it.text)
            if hit is not None:
                self._deliver(gen, it.n, "done", hit, "cache")
                continue
            if self.config.get("localDict", True) and target == "en":
                g = self.dictionary.lookup(it.text)
                if g:
                    # Shown at once. A dictionary gloss is the first sense of a word, which is sometimes the wrong
                    # one (加油 → "add oil"); with a service set up, it rides along in the list's request and the
                    # service's answer replaces it (and is cached, so next time it is instant and right).
                    self._deliver(gen, it.n, "done", g, "dict")
                    provisional[it.n] = it.text
                    continue
            waiting[it.n] = it.text
        state = self._baseline_state()
        if state not in ("localOnly", "noService"):
            waiting.update(provisional)
        if not waiting:
            return
        if state in ("localOnly", "noService"):
            self._set_state(state)
            reason = "noEntryLang" if target != "en" and self.config.get("localDict", True) else "noEntry"
            for n in waiting:
                self._deliver(gen, n, "noEntry", None, None, reason)
            return
        busy = self._inflight.get(target, set())
        rest = {n: t for n, t in waiting.items() if t not in busy}  # the others are filled when that call returns
        if rest and not self._warm_sent:
            # First keystroke that needs the service: open the TLS connection now (≈ 0.5 s), during the typing pause.
            self._warm_sent = True
            self._jobs.put({"warm": dict(self.svc)})
        if rest:
            self._pending[gen] = rest
            self._sched.at(DEBOUNCE_MS / 1000, {"type": "_svc_flush", "gen": gen, "target": target})

    def retry(self, gen: int, n: int, text: str, target: str) -> None:
        self._latest = max(self._latest, gen)
        self._submit(gen, {n: text}, target)

    def accept(self, ev: dict) -> None:
        if ev["type"] == "_svc_flush":
            texts = self._pending.pop(ev["gen"], None)
            if texts and ev["gen"] == self._latest:
                self._submit(ev["gen"], texts, ev["target"])
            self._pending = {g: t for g, t in self._pending.items() if g >= self._latest}
        elif ev["type"] == "_svc_result":
            self._result(ev)
        elif ev["type"] == "_svc_hedge":
            self._hedge(ev["job"])
        elif ev["type"] == "_cache_save":
            self._save_due = False
            try:
                self.cache.save()
            except OSError:
                log.error("cache save failed")

    def _submit(self, gen: int, texts: dict[int, str], target: str) -> None:
        self._inflight.setdefault(target, set()).update(texts.values())
        key = secrets.get_key(self.svc["provider"]) if providers.needs_key(self.svc) else ""
        self._job_id += 1
        self._open[self._job_id] = 1
        job = {"id": self._job_id, "gen": gen, "texts": texts, "target": target, "svc": dict(self.svc), "key": key,
               "timeout": float(self.config.get("timeout", 8) or 8)}
        self._jobs.put(job)
        # Tail latency: OpenCode Go answers in ≈ 1.5 s but occasionally hangs until the timeout (live run: 8 s).
        self._sched.at(HEDGE_S, {"type": "_svc_hedge", "job": {**job, "key": ""}})

    def _hedge(self, job: dict) -> None:
        if self._open.get(job["id"]) != 1 or job["gen"] != self._latest:
            return  # answered already, or that list is gone
        self._open[job["id"]] = 2
        key = secrets.get_key(self.svc["provider"]) if providers.needs_key(self.svc) else ""
        self._jobs.put({**job, "key": key, "hedge": True})

    def _worker(self) -> None:
        while True:
            job = self._jobs.get()
            if job is None:
                return
            if "warm" in job:
                try:
                    providers.warm(job["warm"])
                except Exception:  # noqa: BLE001 — best effort; the request reports real errors
                    pass
                continue
            if job.get("hedge") and self._open.get(job["id"]) is None:
                continue  # the original answered while this copy waited
            if not job.get("hedge") and job["gen"] < self._latest and len(job["texts"]) > 1:
                # Replaced before we got to it (typing on). Single-item retries always run.
                self._post({"type": "_svc_result", "job": {**job, "key": ""}, "skipped": True})
                continue
            t0 = time.perf_counter()
            try:
                out = providers.translate(job["svc"], job["key"], job["texts"], job["target"], job["timeout"], hedge=bool(job.get("hedge")))
                res = {"out": out}
            except HttpError as e:
                res = {"error": e.kind, "status": e.status, "conn": getattr(e, "conn", "")}
                if e.kind == "timeout":
                    providers.new_session()
            except Exception as e:  # noqa: BLE001 — classification only; messages could carry text
                res = {"error": "internal", "status": 0, "exc": type(e).__name__}
            job["key"] = ""
            self._post({"type": "_svc_result", "job": job, "ms": round((time.perf_counter() - t0) * 1000), **res})

    def _result(self, ev: dict) -> None:
        job = ev["job"]
        target, texts = job["target"], job["texts"]
        jid = job.get("id")
        if ev.get("skipped"):
            self._open.pop(jid, None)
        elif jid is not None:
            left = self._open.get(jid)
            if left is None:  # another copy of this request already answered: keep the result for the cache only
                for n, t in texts.items():
                    if n in ev.get("out", {}):
                        self.cache.put(target, t, ev["out"][n])
                return
            if "error" in ev and left > 1:
                self._open[jid] = left - 1  # the other copy may still succeed
                return
            del self._open[jid]
        self._inflight.get(target, set()).difference_update(texts.values())
        cur = self._current()
        if ev.get("skipped"):
            # Still wanted after all (e.g. same texts in the current list)? Re-request them.
            if cur and cur.gen == self._latest:
                again = {it.n: it.text for it in cur.items if it.state == "loading" and it.text in texts.values()}
                if again:
                    self._submit(cur.gen, again, target)
            return
        if "error" in ev:
            kind = ev["error"]
            log.info("service error kind=%s status=%s items=%d ms=%s conn=%s hedge=%s", kind, ev.get("status"), len(texts), ev.get("ms"), ev.get("conn", ""), bool(job.get("hedge")))
            self._set_state({"network": "offline", "timeout": "offline", "auth": "auth"}.get(kind, "failed"))
            reason = {"timeout": "timeout", "network": "network"}.get(kind, kind)
            if cur:
                for it in cur.items:
                    if it.state == "loading" and it.text in texts.values():
                        self._deliver(cur.gen, it.n, "failed", None, None, reason)
            return
        self._warm_sent = False  # the next composition re-checks; warm() is a no-op while a connection is fresh
        out: dict[int, str] = ev["out"]
        log.info("service ok items=%d translated=%d ms=%s hedge=%s", len(texts), len(out), ev.get("ms"), bool(job.get("hedge")))
        self._set_state("ok")
        by_text = {}
        for n, t in texts.items():
            if n in out:
                by_text[t] = out[n]
                self.cache.put(target, t, out[n])
        if self.cache.dirty and not self._save_due:
            self._save_due = True
            self._sched.at(5.0, {"type": "_cache_save"})
        if cur:
            for it in cur.items:
                if it.text not in texts.values():
                    continue
                tr = by_text.get(it.text)
                if it.state == "loading":
                    if tr is not None:
                        self._deliver(cur.gen, it.n, "done", tr, "ai")
                    else:
                        self._deliver(cur.gen, it.n, "failed", None, None, "parse")
                elif it.source == "dict" and tr is not None and tr != it.translation:
                    self._deliver(cur.gen, it.n, "done", tr, "ai")  # refine the provisional dictionary gloss

    # ---- settings actions --------------------------------------------------------------------
    def close(self) -> None:
        for _ in range(2):
            self._jobs.put(None)
        try:
            self.cache.save()
        except OSError:
            pass
        self.dictionary.close()
