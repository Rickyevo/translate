"""Candidate-bar detection inside WeType's transparent canvas, independent of WeType version, layout, DPI and flips.

Synthetic BGRA renders (what PrintWindow returns: transparent parts black) with the bar drawn where different WeType
setups draw it. No IME, no screen, no input.
Run from backend/:  python -X utf8 -m unittest tests.test_bar_detection
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from translate_backend import win32  # noqa: E402


def render(w: int, h: int, boxes: list[tuple[int, int, int, int, tuple[int, int, int]]]) -> bytes:
    """A w×h BGRA buffer, black (transparent) except for filled boxes (x, y, bw, bh, (r, g, b))."""
    buf = bytearray(w * h * 4)
    for i in range(3, len(buf), 4):
        buf[i] = 255
    for x, y, bw, bh, (r, g, b) in boxes:
        for yy in range(y, y + bh):
            for xx in range(x, x + bw):
                o = (yy * w + xx) * 4
                buf[o:o + 3] = bytes((b, g, r))
    return bytes(buf)


def scaled(v, s):
    return round(v * s)


class InkBox(unittest.TestCase):
    def test_layouts_and_scales(self):
        cases = {
            # (canvas at 96 dpi 628×314) bar box at 96 dpi, colour
            "3.0 single line (this PC)": ((27, 136, 574, 43), (250, 250, 250)),
            "2.1 pinyin line above": ((20, 109, 588, 70), (250, 250, 250)),
            "flipped: bar at the bottom of the canvas": ((27, 260, 574, 43), (250, 250, 250)),
            "flipped: bar at the top of the canvas": ((27, 4, 574, 43), (250, 250, 250)),
            "dark skin": ((27, 136, 574, 43), (40, 42, 46)),
            "short list, narrow bar": ((27, 136, 180, 43), (250, 250, 250)),
        }
        for scale in (1.0, 1.25, 1.5, 2.0):
            w, h = scaled(628, scale), scaled(314, scale)
            for name, (box, colour) in cases.items():
                with self.subTest(name=name, scale=scale):
                    want = tuple(scaled(v, scale) for v in box)
                    got = win32.ink_bbox(render(w, h, [(*want, colour)]), w, h)
                    self.assertEqual(got, want)
                    self.assertTrue(win32.plausible_bar(got, w, h, scale))

    def test_text_on_a_black_skin_still_found(self):
        # A pure-black bar: only its text is "drawn" — the box shrinks to the text, still a usable anchor.
        w, h = 628, 314
        got = win32.ink_bbox(render(w, h, [(40, 150, 300, 18, (230, 230, 230))]), w, h)
        self.assertEqual(got, (40, 150, 300, 18))
        self.assertTrue(win32.plausible_bar(got, w, h, 1.0))

    def test_implausible(self):
        w, h = 628, 314
        self.assertFalse(win32.plausible_bar(None, w, h, 1.0))  # nothing drawn yet
        self.assertFalse(win32.plausible_bar((0, 0, w, h), w, h, 1.0))  # whole canvas (no transparency)
        self.assertFalse(win32.plausible_bar((10, 10, 30, 30), w, h, 1.0))  # a speck, not a bar
        self.assertFalse(win32.plausible_bar((10, 10, 500, 300), w, h, 1.0))  # taller than a bar can be


class BarFallback(unittest.TestCase):
    def setUp(self):
        win32._bar_cache.clear()
        win32._bar_last.clear()

    def bar(self, buf, size=(628, 314), scale=1.0, hwnd=1):
        rect = {"x": 1000, "y": 500, "w": size[0], "h": size[1]}
        with mock.patch.object(win32, "_render", return_value=buf):
            return win32.wetype_bar(hwnd, rect, scale)

    def test_measured_then_last_known_then_default(self):
        drawn = render(628, 314, [(27, 136, 574, 43, (250, 250, 250))])
        blank = render(628, 314, [])
        self.assertEqual(self.bar(drawn), ((27, 136, 574, 43), True))
        win32._bar_cache.clear()
        # Next show: not drawn yet → the last box measured at this size, flagged as not measured.
        self.assertEqual(self.bar(blank), ((27, 136, 574, 43), False))
        # A size never measured (another DPI): the default band, scaled.
        box, measured = self.bar(render(942, 471, []), size=(942, 471), scale=1.5)
        self.assertFalse(measured)
        self.assertEqual(box, (0, 164, 942, 105))

    def test_render_failure_falls_back(self):
        box, measured = self.bar(None)
        self.assertFalse(measured)
        self.assertEqual(box, (0, 109, 628, 70))


if __name__ == "__main__":
    unittest.main()
