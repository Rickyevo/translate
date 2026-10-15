"""Local Chinese → English dictionary (CC-CEDICT, see data/cedict.LICENSE).

data/cedict.tsv is sorted by UTF-8 bytes ("headword<TAB>gloss" per line). Lookups binary-search the memory-mapped file,
so the 2.8 MB file costs shared, evictable page cache rather than private memory, and opening it is instant.
"""
from __future__ import annotations

import mmap
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "data" / "cedict.tsv"


class Dictionary:
    def __init__(self, path: Path = PATH):
        self._path = path
        self._mm: mmap.mmap | None = None

    def _map(self) -> mmap.mmap | None:
        if self._mm is None and self._path.exists():
            with open(self._path, "rb") as f:
                self._mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        return self._mm

    def _find(self, word: str) -> bytes | None:
        mm = self._map()
        if mm is None:
            return None
        key = word.encode("utf-8") + b"\t"
        lo, hi = 0, len(mm)
        while lo < hi:
            mid = (lo + hi) // 2
            start = mm.rfind(b"\n", 0, mid) + 1
            end = mm.find(b"\n", start)
            end = len(mm) if end < 0 else end
            line = mm[start:end]
            head = line.split(b"\t", 1)[0] + b"\t"
            if head == key:
                return line[len(key):]
            if head < key:
                lo = end + 1
            else:
                hi = start
        return None

    def lookup(self, word: str) -> str | None:
        """Short English gloss, or None if the word isn't a headword with a usable gloss."""
        g = self._find(word)
        return g.decode("utf-8") if g else None

    def is_headword(self, word: str) -> bool:
        return self._find(word) is not None

    def close(self) -> None:
        if self._mm is not None:
            self._mm.close()
            self._mm = None
