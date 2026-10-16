"""Microsoft Pinyin source and input-method selection, through the replay source: synthetic UI Automation snapshots
(what the observer posts), DryInput for insertion — nothing attaches to an input method or types on the desktop."""
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
from translate_backend.simtranslate import MARK

FG = {"hwnd": 1, "pid": 4242, "exe": "replay-target.exe"}
BAR = {"x": 251, "y": 219, "w": 579, "h": 36}
WIN = {"x": 241, "y": 201, "w": 599, "h": 72}


class Harness(unittest.TestCase):
    mode = "auto"

    def setUp(self):
        self.out = io.BytesIO()
        p = patch.object(protocol, "_stdout", self.out)
        p.start()
        self.addCleanup(p.stop)
        self.b = Backend(True, source="mspy-replay")
        self.addCleanup(self.b.scheduler.close)
        self.b.handle({"type": "config.set", "config": {"target": "en", "count": 5, "denylist": [], "ime": self.mode}})
        self.dbg("debug.mspy.connection", state="connected")
        self.dbg("debug.wetype.connection", state="connected")

    def dbg(self, t, **f):
        self.b.handle({"type": t, **f})

    def show(self, texts, rect=BAR, fg=FG):
        self.dbg("debug.mspy.list", texts=list(texts), rect=rect, canvas=WIN, foreground=fg)
        cl = self.b.source.current
        return cl.gen if cl else None

    def msgs(self, t=None):
        lines = [json.loads(x) for x in self.out.getvalue().decode().splitlines()]
        return [m for m in lines if t is None or m["type"] == t]

    def pump(self, seconds=0.4):
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


class MsPinyinTests(Harness):
    def test_list_window_and_generations(self):
        gen = self.show(["时", "是", "事", "市", "使", "式", "世"])
        cands = self.msgs("candidates")
        self.assertEqual(cands[-1]["gen"], gen)
        self.assertEqual([i["text"] for i in cands[-1]["items"]], ["时", "是", "事", "市", "使"])  # count 5 of 7
        a = cands[-1]["anchor"]
        self.assertEqual((a["x"], a["y"], a["w"], a["h"]), (BAR["x"], BAR["y"], BAR["w"], BAR["h"]))
        self.assertEqual(a["canvas"], WIN)
        # A keystroke: a different list is a new generation, and the composition continues.
        gen2 = self.show(["时间", "事件", "实践"])
        self.assertEqual(gen2, gen + 1)
        self.assertEqual(self.msgs("composition.end"), [])
        # Same list, window moved: a reposition, not a new generation.
        n = len(self.msgs("candidates"))
        self.assertEqual(self.show(["时间", "事件", "实践"], rect={**BAR, "x": 300}), gen2)
        self.assertEqual(len(self.msgs("candidates")), n + 1)
        self.assertEqual(self.msgs("candidates")[-1]["anchor"]["x"], 300)

    def test_window_closes_ends_the_composition(self):
        gen = self.show(["时间", "事件"])
        self.dbg("debug.mspy.close")
        self.assertEqual(self.msgs("composition.end")[-1]["gen"], gen)
        self.assertIsNone(self.b.source.current)
        self.assertFalse(self.b.source.composing)

    def test_insert_cancels_with_esc_then_types(self):
        gen = self.show(["时间", "事件", "实践"])
        self.pump()
        self.b.handle({"type": "insert", "id": 9, "gen": gen, "n": 1})
        r = self.msgs("insert.result")[-1]
        self.assertTrue(r["ok"], r)
        self.assertEqual(self.b.input.log, [{"key": 0x1B}, {"text": MARK + "time"}])  # Esc strictly before the text
        self.assertFalse(self.b.source.composing)

    def test_focus_change_and_password_end_it(self):
        self.show(["时间"])
        self.dbg("debug.mspy.list", texts=["时间"], rect=BAR, foreground={**FG, "hwnd": 2})
        self.assertEqual(len(self.msgs("composition.end")), 1)  # the old app's composition ended
        self.show(["时间"], fg={**FG, "password": True})
        self.assertIsNone(self.b.source.current)

    def test_denylist(self):
        self.b.handle({"type": "config.set", "config": {"target": "en", "count": 5, "denylist": ["replay-target"], "ime": "auto"}})
        self.assertIsNone(self.show(["时间"]))


class SelectionTests(Harness):
    def test_each_connection_and_mode_change_is_reported(self):
        self.dbg("debug.mspy.connection", state="failed")
        self.assertEqual(self.msgs("status")[-1]["ime"]["all"], {"wetype": "connected", "mspinyin": "failed"})
        self.dbg("debug.mspy.connection", state="connected")
        self.assertEqual(self.msgs("status")[-1]["ime"]["all"]["mspinyin"], "connected")
        self.b.handle({"type": "config.set", "config": {"target": "en", "count": 5, "denylist": [], "ime": "wetype"}})
        self.assertEqual(self.msgs("status")[-1]["ime"]["all"], {"wetype": "connected"})

    def test_auto_follows_the_composing_input_method(self):
        # WeType composes first…
        self.dbg("debug.wetype.window", rect={"x": 100, "y": 200, "w": 600, "h": 46}, foreground=FG)
        self.dbg("debug.wetype.bytes", steps=[{"k": "comp", "pinyin": "shi"}, {"k": "list", "words": ["时间", "事件"]}])
        self.assertEqual(self.b.source.active.name, "wetype")
        wgen = self.b.source.current.gen
        # …then Microsoft Pinyin opens its window: it takes over and WeType's composition ends.
        self.show(["你好", "您好"])
        self.assertEqual(self.b.source.active.name, "mspinyin")
        self.assertIn(wgen, [m["gen"] for m in self.msgs("composition.end")])
        self.assertEqual([i.text for i in self.b.source.current.items], ["你好", "您好"])
        self.assertGreater(self.b.source.current.gen, wgen)  # newer than WeType's last list: the host shows it

    def test_status_names_the_input_method(self):
        st = [m["ime"] for m in self.msgs("status") if "ime" in m]
        self.assertTrue(any(s["state"] == "connected" for s in st))
        self.assertEqual(set(st[-1]["all"]), {"wetype", "mspinyin"})


class OnlyMsPinyin(Harness):
    mode = "mspinyin"

    def test_wetype_not_running(self):
        self.assertEqual(set(self.b.source.sources), {"mspinyin"})
        self.dbg("debug.wetype.bytes", steps=[{"k": "comp", "pinyin": "shi"}, {"k": "list", "words": ["时间"]}])
        self.assertIsNone(self.b.source.current)  # WeType events are ignored
        self.assertIsNotNone(self.show(["时间"]))


class OnlyWeType(Harness):
    mode = "wetype"

    def test_mspinyin_not_running(self):
        self.assertEqual(set(self.b.source.sources), {"wetype"})
        self.assertIsNone(self.show(["时间"]))


if __name__ == "__main__":
    unittest.main()
