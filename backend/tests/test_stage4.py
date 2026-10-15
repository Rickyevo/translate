"""Stage 4: real-candidate integration through the replay source. Synthetic bytes only; DryInput records
what would be typed, so nothing is sent to the desktop and nothing attaches to the IME."""
from pathlib import Path
import io
import json
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from translate_backend import protocol
from translate_backend.__main__ import Backend
from translate_backend.simtranslate import MARK, Scheduler, simulate
from translate_backend.wetype import encode

FG = {"hwnd": 1, "pid": 4242, "exe": "replay-target.exe"}
RECT = {"x": 100, "y": 200, "w": 600, "h": 46}


class Harness(unittest.TestCase):
    def setUp(self):
        self.out = io.BytesIO()
        p = patch.object(protocol, "_stdout", self.out)
        p.start()
        self.addCleanup(p.stop)
        self.b = Backend(True, source="wetype-replay")
        self.addCleanup(self.b.scheduler.close)
        self.b.handle({"type": "config.set", "config": {"target": "en", "count": 5, "denylist": []}})
        self.dbg("debug.wetype.connection", state="connected")
        self.dbg("debug.wetype.window", rect=RECT, foreground=FG)

    def dbg(self, t, **f):
        self.b.handle({"type": t, **f})

    def keys(self, *steps):
        self.dbg("debug.wetype.bytes", steps=list(steps))

    def msgs(self, t=None):
        lines = [json.loads(x) for x in self.out.getvalue().decode().splitlines()]
        return [m for m in lines if t is None or m["type"] == t]

    def pump(self, seconds=0.4):
        """Run the dispatch loop's queue for a while (scheduler deliveries, deferred messages)."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            try:
                m = self.b._backlog.popleft() if self.b._backlog else self.b.events.get(timeout=0.02)
            except Exception:
                continue
            if m is None:
                continue
            if m["type"] == "_source":
                self.b.source.accept(m["event"])
            elif m["type"] == "_translation":
                self.b._translation(m)
            else:
                self.b.handle(m)

    def compose(self, pinyin="shi", words=("时间", "事件", "实践")):
        self.keys({"k": "comp", "pinyin": pinyin}, {"k": "list", "words": list(words)})
        return self.b.source.current.gen


class TranslationTests(Harness):
    def test_simulated_results_marked_and_ordered(self):
        gen = self.compose()
        self.pump()
        tr = [m for m in self.msgs("translation") if m["gen"] == gen]
        self.assertEqual([m["n"] for m in tr], [1, 2, 3])
        self.assertTrue(all(m["text"].startswith(MARK) and m["source"] == "sim" and m["simulated"] for m in tr))
        self.assertEqual(tr[0]["text"], MARK + "time")

    def test_stale_results_rejected(self):
        old = self.compose()
        new = self.compose("shij", ["时间", "世界"])
        self.pump()
        gens = {m["gen"] for m in self.msgs("translation")}
        self.assertEqual(gens, {new})
        self.assertGreaterEqual(self.b.stale_results, 3)
        self.assertNotEqual(old, new)

    def test_reposition_keeps_gen_and_does_not_retranslate(self):
        gen = self.compose()
        self.pump()
        n = len(self.msgs("translation"))
        self.dbg("debug.wetype.window", rect={**RECT, "x": 300}, foreground=FG)
        self.pump(0.2)
        lists = self.msgs("candidates")
        self.assertEqual([m["gen"] for m in lists], [gen, gen])
        self.assertEqual(lists[-1]["anchor"]["x"], 300)
        self.assertEqual(len(self.msgs("translation")), n)

    def test_keystrokes_do_not_end_composition(self):
        self.compose("s", ["是"])
        self.compose("sh", ["说"])
        self.compose("shi", ["是", "时"])
        self.assertEqual(self.msgs("composition.end"), [])
        self.keys({"k": "commit"})
        self.assertEqual(len(self.msgs("composition.end")), 1)

    def test_target_language(self):
        self.assertEqual(simulate("时间", "ja"), MARK + "時間")
        self.assertEqual(simulate("未知词", "ko"), MARK + "未知词")

    def test_scheduler_order(self):
        got = []
        s = Scheduler(got.append)
        s.at(0.05, {"i": 2})
        s.at(0.01, {"i": 1})
        time.sleep(0.15)
        s.close()
        self.assertEqual(got, [{"i": 1}, {"i": 2}])


class InsertTests(Harness):
    def ready_list(self):
        gen = self.compose()
        self.pump()
        return gen

    def insert(self, gen, n=1):
        self.b.handle({"type": "insert", "id": 9, "gen": gen, "n": n})
        return self.msgs("insert.result")[-1]

    def typed(self):
        return self.b.input.log

    def test_cancels_composition_then_types(self):
        gen = self.ready_list()
        r = self.insert(gen)
        self.assertTrue(r["ok"], r)
        self.assertEqual(self.typed(), [{"key": 0x1B}, {"text": MARK + "time"}])  # Esc strictly before text
        self.assertEqual(self.msgs("composition.end")[-1]["gen"], gen)
        self.assertFalse(self.b.source.composing)

    def test_cancel_confirmed_by_window_hide(self):
        gen = self.ready_list()
        self.dbg("debug.input", onEscape="hide")
        self.assertTrue(self.insert(gen)["ok"])

    def test_ime_ignores_escape_nothing_typed(self):
        gen = self.ready_list()
        self.dbg("debug.input", onEscape="none")
        t = time.monotonic()
        r = self.insert(gen)
        self.assertEqual(r["error"], "ime")
        self.assertLess(time.monotonic() - t, 1.0)
        self.assertEqual(self.typed(), [{"key": 0x1B}])

    def test_modifiers_still_held(self):
        gen = self.ready_list()
        self.dbg("debug.input", held=["alt"])
        r = self.insert(gen)
        self.assertEqual(r["error"], "modifiers")
        self.assertEqual(self.typed(), [{"key": 0xE8}])  # the Alt-guard tap only; no Esc (would be Alt+Esc)

    def test_stale_and_unavailable(self):
        gen = self.compose()
        self.assertEqual(self.insert(gen)["error"], "unavailable")  # still loading
        self.pump()
        self.keys({"k": "comp", "pinyin": "shij"})  # keystroke: old list invalid before its replacement
        self.assertEqual(self.insert(gen)["error"], "stale")
        self.assertEqual(self.typed(), [])

    def test_focus_moved(self):
        gen = self.ready_list()
        self.dbg("debug.wetype.window", rect=RECT, foreground={**FG, "hwnd": 2})
        self.assertEqual(self.insert(gen)["error"], "stale")
        self.assertEqual(self.typed(), [])

    def test_denylist(self):
        gen = self.ready_list()
        self.b.source.config["denylist"] = ["replay-target"]
        self.assertEqual(self.insert(gen)["error"], "denied")

    def test_messages_during_wait_are_deferred_in_order(self):
        gen = self.ready_list()
        self.dbg("debug.input", onEscape="none")
        self.b.events.put({"type": "ping", "id": 1})
        self.b.events.put({"type": "ping", "id": 2})
        self.insert(gen)
        self.assertEqual([m["id"] for m in self.b._backlog], [1, 2])


class ConnectionTests(Harness):
    def test_reconnect_ends_composition_and_requires_fresh_one(self):
        gen = self.compose()
        self.dbg("debug.wetype.connection", state="waiting", code="ProcessNotFoundError")
        self.assertEqual(self.msgs("composition.end")[-1]["gen"], gen)
        self.assertEqual(self.msgs("status")[-1]["ime"]["state"], "waiting")
        self.dbg("debug.wetype.connection", state="connected")
        self.keys({"k": "list", "words": ["旧"]})  # mid-composition list from the new session: ignored
        self.assertIsNone(self.b.source.current)
        self.compose("ni", ["你"])
        self.assertIsNotNone(self.b.source.current)

    def test_old_epoch_bytes_ignored(self):
        epoch = self.b.source._epoch
        self.dbg("debug.wetype.connection", state="connected")
        self.dbg("debug.wetype.bytes", steps=[{"k": "comp", "pinyin": "ni"}, {"k": "list", "words": ["你"]}], epoch=epoch)
        self.assertIsNone(self.b.source.current)

    def test_fragmented_writes(self):
        self.dbg("debug.wetype.bytes", steps=[{"k": "comp", "pinyin": "ni"}, {"k": "list", "words": ["你", "呢"]}], chunk=3)
        self.assertEqual([c.text for c in self.b.source.current.items], ["你", "呢"])


class WindowEventsTests(unittest.TestCase):
    """The event-driven watcher, against a real top-level window of this process (not the IME)."""

    def test_show_move_hide_wake_the_watcher(self):
        import ctypes
        import threading
        from ctypes import wintypes as wt
        from translate_backend import win32
        u = ctypes.WinDLL("user32", use_last_error=True)
        u.CreateWindowExW.restype = wt.HWND
        u.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID]
        u.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
        u.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
        u.DestroyWindow.argtypes = [wt.HWND]
        WS_POPUP, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW = 0x80000000, 0x08000000, 0x80
        hwnd = u.CreateWindowExW(WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW, "STATIC", "translate-test-candidate", WS_POPUP, -3000, -3000, 200, 300, None, None, None, None)
        self.assertTrue(hwnd)
        hits = []
        w = win32.WindowEvents(lambda: int(hwnd), lambda: hits.append(win32.window_rect(int(hwnd)) if u.IsWindowVisible(hwnd) else None),
                               flags=win32.WINEVENT_OUTOFCONTEXT)
        th = threading.Thread(target=w.run, daemon=True)
        th.start()
        try:
            time.sleep(0.3)
            n = len(hits)
            u.ShowWindow(hwnd, 4)  # SW_SHOWNOACTIVATE
            time.sleep(0.2)
            u.SetWindowPos(hwnd, None, -2900, -3000, 200, 300, 0x10 | 0x4)  # NOACTIVATE | NOZORDER
            time.sleep(0.2)
            u.ShowWindow(hwnd, 0)
            time.sleep(0.2)
            seen = hits[n:]
            self.assertTrue(any(r and r["x"] == -3000 for r in seen), "show not seen")
            self.assertTrue(any(r and r["x"] == -2900 for r in seen), "move not seen")
            self.assertIsNone(seen[-1], "hide not seen")
        finally:
            w.stop()
            th.join(2)
            u.DestroyWindow(hwnd)
        self.assertFalse(th.is_alive())


if __name__ == "__main__":
    unittest.main()
