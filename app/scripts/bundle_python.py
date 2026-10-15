"""Build the isolated Python runtime that ships inside the release (resources/python/).

From the local CPython 3.12 install (no download):
  TranslateEngine.exe         python.exe, renamed so Task Manager shows what it is
  python312.dll, python3.dll  core runtime
  vcruntime140*.dll           MSVC runtime (machines without the VC++ redistributable)
  python312.zip               the standard library as precompiled .pyc (minus GUI, tests, tooling)
  DLLs/                       only the extension modules the backend needs (+ OpenSSL, libffi)
  python312._pth              isolation: sys.path is exactly the entries listed; PYTHONPATH/PYTHONHOME, the
                              user site and any installed Python are ignored; `site` is not imported
  LICENSE.txt                 Python Software Foundation license
The backend (resources/backend) is precompiled too, for startup time.
Run: python -X utf8 scripts/bundle_python.py <stage-dir> <backend-stage-dir>
"""
from __future__ import annotations

import compileall
import os
import py_compile
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

if sys.version_info[:2] != (3, 12):
    sys.exit("build the runtime with CPython 3.12 (the backend and vendored Frida target 3.12)")

SRC = Path(sys.base_prefix)
CORE = ["python312.dll", "python3.dll", "vcruntime140.dll", "vcruntime140_1.dll", "LICENSE.txt"]
DLLS = ["_ctypes.pyd", "libffi-8.dll", "_socket.pyd", "select.pyd", "_ssl.pyd", "_hashlib.pyd", "libssl-3.dll",
        "libcrypto-3.dll", "_queue.pyd", "unicodedata.pyd", "_overlapped.pyd", "_asyncio.pyd", "_uuid.pyd",
        "_bz2.pyd", "_lzma.pyd", "_decimal.pyd", "pyexpat.pyd", "_elementtree.pyd", "_multiprocessing.pyd",
        "_zoneinfo.pyd"]
SKIP_DIRS = {"test", "tests", "idlelib", "tkinter", "turtledemo", "ensurepip", "lib2to3", "pydoc_data", "venv",
             "site-packages", "__pycache__", "sqlite3", "msilib", "curses", "dbm", "unittest", "__phello__"}
SKIP_FILES = {"turtle.py", "antigravity.py", "this.py"}


def build(stage: Path, backend: Path) -> None:
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True)
    shutil.copy2(SRC / "python.exe", stage / "TranslateEngine.exe")
    for f in CORE:
        shutil.copy2(SRC / f, stage / f)
    (stage / "DLLs").mkdir()
    for f in DLLS:
        shutil.copy2(SRC / "DLLs" / f, stage / "DLLs" / f)

    # Standard library → python312.zip of legacy-layout .pyc files (zipimport reads them directly).
    lib = SRC / "Lib"
    n = 0
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(stage / "python312.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(lib):
            rel_root = Path(root).relative_to(lib)
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                if not f.endswith(".py") or f in SKIP_FILES:
                    continue
                rel = rel_root / f
                out = Path(tmp) / "m.pyc"
                try:
                    py_compile.compile(str(Path(root) / f), cfile=str(out), dfile=str(rel), doraise=True, optimize=0)
                except py_compile.PyCompileError:
                    continue
                z.write(out, str(rel.with_suffix(".pyc")).replace("\\", "/"))
                n += 1

    # Isolation: exactly these paths, relative to this folder; no site, no environment, no user site.
    (stage / "python312._pth").write_text("python312.zip\nDLLs\n..\\backend\n..\\backend\\vendor\n", encoding="ascii")

    # Backend: precompile to __pycache__ so the first start doesn't compile (the host runs it with -B).
    compileall.compile_dir(str(backend / "translate_backend"), quiet=1, optimize=0)
    print(f"runtime: {n} stdlib modules, {sum(p.stat().st_size for p in stage.rglob('*') if p.is_file()) / 2**20:.1f} MB")


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2]))
