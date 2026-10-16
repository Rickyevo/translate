"""Production package of the Tauri host: Translate.exe (UI embedded), the Python engine and an isolated Python 3.12
runtime in resources\\ — the release needs no Python, Node or other development tools; the UI runs in the system's
WebView2. Build with CPython 3.12, Node and Rust (MSVC) on PATH.
Run from app/:  python -X utf8 scripts/package.py [--out=release-build]
Output: <out>/Translate-win32-x64/
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
OUT = Path(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--out=")), "release-build"))
if not OUT.is_absolute():
    OUT = APP / OUT
DEST = OUT / "Translate-win32-x64"
STAGE = ROOT / ".cache" / "package-stage"


def run(cmd: list[str], cwd: Path = APP):
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True, shell=cmd[0] in ("npx", "npm"))


def rust_notices() -> str:
    """License notices for every Rust crate compiled into Translate.exe (normal dependencies of the binary)."""
    meta = json.loads(subprocess.run(["cargo", "metadata", "--format-version", "1", "--filter-platform", "x86_64-pc-windows-msvc"],
                                     cwd=APP / "src-tauri", check=True, capture_output=True, text=True).stdout)
    pkgs = {p["id"]: p for p in meta["packages"]}
    nodes = {n["id"]: n for n in meta["resolve"]["nodes"]}
    root = meta["resolve"]["root"]
    seen, stack = set(), [root]
    while stack:
        i = stack.pop()
        if i in seen:
            continue
        seen.add(i)
        for d in nodes[i]["deps"]:
            if any(k.get("kind") in (None, "normal") for k in d["dep_kinds"]):
                stack.append(d["pkg"])
    seen.discard(root)
    out = ["Rust crates compiled into Translate.exe, with their licenses.", ""]
    texts: dict[str, list[str]] = {}
    for i in sorted(seen, key=lambda i: (pkgs[i]["name"], pkgs[i]["version"])):
        p = pkgs[i]
        out.append(f"{p['name']} {p['version']} — {p.get('license') or p.get('license_file') or 'see crate'}  {p.get('repository') or ''}".rstrip())
        d = Path(p["manifest_path"]).parent
        for f in sorted(d.iterdir()):
            if f.is_file() and f.name.upper().startswith(("LICENSE", "LICENCE", "COPYING", "NOTICE")):
                t = f.read_text(encoding="utf-8", errors="replace").strip()
                texts.setdefault(t, []).append(f"{p['name']} {p['version']} ({f.name})")
    out += ["", "=" * 78, "License texts (each followed by the crates it ships with)", "=" * 78]
    for t, who in texts.items():
        out += ["", "-" * 78, "Applies to: " + ", ".join(who), "-" * 78, t]
    return "\n".join(out) + "\n"


def main():
    run(["node", "scripts/gen_defaults.mjs"])
    run(["npx", "vite", "build"])
    run(["cargo", "build", "--release"], cwd=APP / "src-tauri")
    # Ship only the runtime backend: no tests, no research/capture tools (they can write raw pipe data to disk), no
    # bytecode caches.
    shutil.rmtree(STAGE, ignore_errors=True)
    for part in ("translate_backend", "vendor", "requirements.txt"):
        src = ROOT / "backend" / part
        dst = STAGE / "backend" / part
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
    run([sys.executable, "-X", "utf8", "scripts/bundle_python.py", str(STAGE / "python"), str(STAGE / "backend")])
    shutil.rmtree(DEST, ignore_errors=True)
    (DEST / "resources").mkdir(parents=True)
    shutil.copyfile(APP / "src-tauri" / "target" / "release" / "Translate.exe", DEST / "Translate.exe")
    shutil.copytree(STAGE / "backend", DEST / "resources" / "backend")
    shutil.copytree(STAGE / "python", DEST / "resources" / "python")
    shutil.copyfile(APP / "build" / "THIRD_PARTY_NOTICES.txt", DEST / "THIRD_PARTY_NOTICES.txt")
    (DEST / "THIRD_PARTY_RUST.txt").write_text(rust_notices(), encoding="utf-8", newline="\r\n")
    size = sum(p.stat().st_size for p in DEST.rglob("*") if p.is_file())
    print(json.dumps({"packaged": str(DEST), "mb": round(size / 2**20, 1)}))


if __name__ == "__main__":
    main()
