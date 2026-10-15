"""Synthetic protocol/state tests. Never attach to an IME or inject keyboard input."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from translate_backend.wetype.protocol import Framer, decode, ListEvent, CompositionEvent, CommitEvent
from translate_backend.wetype.source import WeTypeSource
from translate_backend.__main__ import Backend


def vi(n):
    out = bytearray()
    while n > 127:
        out.append((n & 127) | 128)
        n >>= 7
    return bytes(out) + bytes([n])


def value(field, n):
    return vi(field << 3) + vi(n)


def sub(field, data):
    return vi((field << 3) | 2) + vi(len(data)) + data


def event(kind, body=b""):
    return value(1, 1) + sub(2, value(1, 123) + sub(2, value(1, kind) + body))


def composition(text):
    return event(3, sub(3, sub(1, value(1, 1) + sub(7, text.encode()))))


def candidates(words):
    return event(2, sub(2, b"".join(sub(1, sub(1, text.encode())) for text in words)))


class WireTests(unittest.TestCase):
    def test_order_duplicates_unicode(self):
        self.assertEqual(decode(candidates(["时间", "事件", "😀", "时间"])).texts,
                         ["时间", "事件", "😀", "时间"])

    def test_composition_and_commit(self):
        self.assertEqual(decode(composition("shi")).pinyin, "shi")
        self.assertIsInstance(decode(event(1, sub(4, b"private"))), CommitEvent)
        self.assertEqual(vars(decode(event(1, sub(4, b"private")))), {})

    def test_each_byte_fragmented_and_coalesced(self):
        msg = composition("ni") + candidates(["你好"])
        framer = Framer()
        got = []
        for byte in msg:
            got.extend(framer.feed(bytes([byte])))
        self.assertEqual(len(got), 2)
        self.assertIsInstance(decode(got[0]), CompositionEvent)
        self.assertEqual(decode(got[1]).texts, ["你好"])

    def test_resync_split_header(self):
        msg = candidates(["test"])
        f = Framer()
        self.assertEqual(f.feed(b"garbage" + msg[:2]), [])
        self.assertEqual(f.feed(msg[2:]), [msg])

    def test_buffer_bounded(self):
        f = Framer()
        f.feed(b"x" * (f.MAX * 2))
        self.assertLessEqual(len(f.buf), f.MAX)
        self.assertEqual(f.feed(candidates(["test"])), [candidates(["test"])])


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.output = []
        self.source = WeTypeSource(lambda cl: self.output.append(("list", cl.gen)),
            lambda gen, item: self.output.append(("translation", gen, item.n)),
            lambda gen: self.output.append(("end", gen)), lambda event: None,
            lambda state, code: self.output.append(("status", state)))
        self.source._started = True  # no real worker threads in tests
        self.fg = {"pid": 22, "hwnd": 44, "exe": "test.exe"}
        self.rect = {"x": 100, "y": 200, "w": 600, "h": 46}
        self.source.accept({"kind": "connection", "state": "connected", "epoch": 1})
        self.window(self.rect)
        self.fg_patch = patch("translate_backend.win32.user32.GetForegroundWindow", return_value=44)
        self.fg_patch.start()
        self.addCleanup(self.fg_patch.stop)

    def window(self, rect, fg=None):
        self.source.accept({"kind": "window", "rect": rect, "foreground": fg or self.fg})

    def data(self, raw, epoch=1):
        self.source.accept({"kind": "bytes", "epoch": epoch, "handle": "h", "data": raw})

    def compose(self):
        self.data(composition("shi") + candidates(["时间", "事件", "😀", "时间"]))

    def test_list_without_fake_translations(self):
        self.compose()
        cl = self.source.current
        self.assertEqual([c.text for c in cl.items], ["时间", "事件", "😀", "时间"])
        self.assertTrue(all(c.translation is None and c.state == "loading" for c in cl.items))
        self.assertEqual(cl.anchor, self.rect)

    def test_duplicate_list_no_redraw(self):
        self.compose()
        before = list(self.output)
        self.data(candidates(["时间", "事件", "😀", "时间"]))
        self.assertEqual(before, self.output)

    def test_new_pinyin_invalidates_old_immediately(self):
        self.compose()
        old = self.source.current.gen
        self.data(composition("ni"))
        self.assertIsNone(self.source.current)  # inserts against the old list are refused at once
        # ...but the composition continues: the host keeps the panel until the replacement arrives.
        self.assertNotIn(("end", old), self.output)
        self.data(candidates(["你"]))
        self.assertEqual(self.source.current.gen, old + 1)
        self.data(event(1))
        self.assertEqual([o for o in self.output if o[0] == "end"], [("end", old + 1)])

    def test_commit_and_hide(self):
        self.compose()
        self.data(event(1))
        self.assertIsNone(self.source.current)
        self.compose()
        self.window(None)
        self.assertIsNone(self.source.current)
        self.assertEqual(self.source._framers, {})

    def test_focus_switch_drops_pending_content(self):
        self.compose()
        self.window(self.rect, {**self.fg, "hwnd": 55})
        self.assertIsNone(self.source.current)
        self.assertEqual(self.source._pinyin, "")

    def test_password_and_denylist(self):
        self.source.config["denylist"] = ["TEST"]
        self.compose()
        self.assertIsNone(self.source.current)
        self.source.config["denylist"] = []
        self.window(self.rect, {**self.fg, "password": True})
        self.compose()
        self.assertIsNone(self.source.current)

    def test_pause_and_fresh_composition_required(self):
        self.compose()
        self.source.set_paused(True)
        self.compose()
        self.assertIsNone(self.source.current)
        self.source.set_paused(False)
        self.data(candidates(["old"]))
        self.assertIsNone(self.source.current)
        self.compose()
        self.assertIsNotNone(self.source.current)

    def test_reconnect_rejects_previous_session(self):
        self.compose()
        self.source.accept({"kind": "connection", "state": "connected", "epoch": 2})
        self.compose()
        self.assertIsNone(self.source.current)
        self.data(composition("ni") + candidates(["新"]), epoch=2)
        self.assertEqual(self.source.current.items[0].text, "新")

    def test_position_update_keeps_generation(self):
        self.compose()
        gen = self.source.current.gen
        self.window({**self.rect, "x": -500})
        self.assertEqual(self.source.current.gen, gen)
        self.assertEqual(self.source.current.anchor["x"], -500)

    def test_insertion_target_checked(self):
        self.compose()
        with patch("translate_backend.win32.foreground", return_value={**self.fg, "hwnd": 55}):
            self.assertFalse(self.source.validate_target())

    def test_config_target_and_count(self):
        self.compose()
        self.source.configure({"target": "ko", "count": 1, "denylist": []})
        self.assertIsNone(self.source.current)
        self.compose()
        self.assertEqual(len(self.source.current.items), 1)
        self.assertEqual(self.source.config["target"], "ko")

    def test_resegmented_pinyin_keeps_the_list(self):
        self.data(composition("shijian") + candidates(["时间", "事件"]))
        gen = self.source.current.gen
        self.data(composition("shi'jian"))  # WeType re-segments on its own, no new list
        self.assertIsNotNone(self.source.current)
        self.assertEqual(self.source.current.gen, gen)
        self.data(composition("shi'jia"))  # a real edit still invalidates at once
        self.assertIsNone(self.source.current)

    def test_data_before_window_is_shown_when_window_appears(self):
        self.window(None)
        self.compose()  # WeType writes composition + list before its candidate window is visible
        self.assertIsNotNone(self.source.current)
        self.assertNotIn("list", [o[0] for o in self.output])
        self.window(self.rect)
        self.assertEqual([o for o in self.output if o[0] == "list"], [("list", self.source.current.gen)])
        self.assertEqual(self.source.current.anchor, self.rect)

    def test_hidden_window_before_any_list_keeps_composition(self):
        self.window(None)
        self.data(composition("shi"))
        self.window(None, {**self.fg, "focus": 99})  # unrelated metadata change while nothing is shown
        self.data(candidates(["时间"]))
        self.window(self.rect)
        self.assertEqual(self.source.current.items[0].text, "时间")

    def test_stale_foreground_cache_does_not_drop_data(self):
        self.fg_patch.stop()
        with patch("translate_backend.win32.user32.GetForegroundWindow", return_value=77),              patch("translate_backend.win32.foreground", return_value={**self.fg, "hwnd": 77}):
            self.compose()
        self.fg_patch.start()
        self.assertIsNotNone(self.source.current)
        self.assertEqual(self.source.foreground["hwnd"], 77)

    def test_backend_selects_live_and_test_sources(self):
        self.assertIsInstance(Backend(False).source, WeTypeSource)
        self.assertNotIsInstance(Backend(True).source, WeTypeSource)


if __name__ == "__main__":
    unittest.main()
