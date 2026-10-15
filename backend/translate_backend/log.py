"""Diagnostics on stderr, kept separate from the protocol channel (stdout).

Policy: candidate text, pinyin and translations are never logged, at any level; only counts, generations,
timings and error classifications. TRANSLATE_LOG=debug adds more of those, never text.
"""
from __future__ import annotations

import logging
import os
import sys

_level = logging.DEBUG if os.environ.get("TRANSLATE_LOG", "").lower() == "debug" else logging.INFO
logging.basicConfig(stream=sys.stderr, level=_level, format="%(asctime)s.%(msecs)03d %(levelname).1s %(name)s: %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("backend")
