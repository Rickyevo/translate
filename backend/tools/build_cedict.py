"""Build the compact local dictionary from CC-CEDICT (CC BY-SA 4.0, https://www.mdbg.net/chinese/dictionary?page=cedict).

Input:  the downloaded cedict_1_0_ts_utf-8_mdbg.zip (or the extracted cedict_ts.u8)
Output: translate_backend/data/cedict.tsv — one line per simplified headword, "headword<TAB>short gloss", sorted by
        UTF-8 bytes so the backend can binary-search it through mmap (≈0 private memory), plus cedict.LICENSE.
Gloss: the first usable sense of a common-word entry, without classifiers, cross-references or parentheticals, kept
short for the panel (dictionary glosses read as glosses; the service does phrases and other languages).
Run:  python -I backend/tools/build_cedict.py <path-to-zip-or-u8>
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "translate_backend" / "data"
LINE = re.compile(r"^(\S+) (\S+) \[([^\]]*)\] /(.*)/\s*$")
SKIP = re.compile(r"^(CL:|variant of|old variant|archaic variant|see |see also|abbr\. for|surname |used in |also written|erhua variant|Japanese variant|Taiwan pr\.|pr\.|\(Tw\)|\(old\))", re.I)


def clean(g: str) -> str:
    g = re.sub(r"\([^)]*\)", "", g)          # parentheticals
    g = re.sub(r"\[[^\]]*\]", "", g)          # pinyin references
    g = re.sub(r"\b\S+\|\S+", "", g)          # trad|simp cross references
    g = re.sub(r"\s{2,}", " ", g).strip(" ,;")
    return g


def gloss(senses: list[str]) -> str:
    for s in senses:
        if SKIP.match(s.strip()):
            continue
        g = clean(s.split(";")[0])  # first sub-sense: "we; us; ourselves" → "we"
        g = re.sub(r"^to ", "", g)  # inserted as typed text: "to thank" → "thank"
        if len(g) > 48 and "," in g:
            g = g.split(",")[0].strip()  # "Beijing, capital of …" → "Beijing"
        if g and len(g) <= 48:
            return g
    return ""


def main(src: str) -> None:
    p = Path(src)
    if p.suffix == ".zip":
        with zipfile.ZipFile(p) as z:
            text = z.read(next(n for n in z.namelist() if n.endswith(".u8"))).decode("utf-8")
    else:
        text = p.read_text(encoding="utf-8")
    best: dict[str, tuple[int, str]] = {}
    for line in text.splitlines():
        if line.startswith("#"):
            continue
        m = LINE.match(line)
        if not m:
            continue
        _trad, simp, pinyin, body = m.groups()
        proper = pinyin[:1].isupper()  # capitalized pinyin = proper noun (names, places)
        g = gloss(body.split("/"))
        rank = (2 if proper else 0) + (0 if g else 4)
        if simp not in best or rank < best[simp][0]:
            best[simp] = (rank, g)
    OUT.mkdir(parents=True, exist_ok=True)
    rows = sorted(((k.encode("utf-8"), v[1]) for k, v in best.items() if "\t" not in k and "\n" not in v[1]), key=lambda r: r[0])
    with open(OUT / "cedict.tsv", "wb") as f:
        for k, g in rows:
            f.write(k + b"\t" + g.encode("utf-8") + b"\n")  # empty gloss = known headword without a usable gloss
    (OUT / "cedict.LICENSE").write_text(
        "Local dictionary derived from CC-CEDICT (https://www.mdbg.net/chinese/dictionary?page=cedict),\n"
        "licensed under Creative Commons Attribution-ShareAlike 4.0 (https://creativecommons.org/licenses/by-sa/4.0/).\n"
        "Changes: simplified headwords only, one shortened gloss per headword.\n", encoding="utf-8")
    print(f"{len(rows)} headwords, {sum(1 for _, g in rows if g)} with glosses, {(OUT / 'cedict.tsv').stat().st_size / 2**20:.1f} MB")


if __name__ == "__main__":
    main(sys.argv[1])
