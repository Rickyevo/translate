"""Make the distributable: release/Translate-<version>-win-x64.zip (+ SHA256SUMS.txt) from a packaged build.

The zip holds one folder, Translate-<version>-win-x64/, with Translate.exe, the bundled Python runtime and backend,
license notices and README-FIRST.txt. Portable: unzip anywhere and run; no installer, no admin rights, no Python or
other tools needed. Run from app/:  python -X utf8 scripts/make_release.py <packaged folder>
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = json.loads((ROOT / "app" / "package.json").read_text(encoding="utf-8"))["version"]
NAME = f"Translate-{VERSION}-win-x64"

README = f"""Translate {VERSION} — translation companion for WeChat Input Method (Windows 10/11, x64)

START
  Unzip this folder anywhere you like (for example %LOCALAPPDATA%\\Programs\\Translate) and run Translate.exe.
  Nothing appears at first: Translate runs quietly in the background. Type pinyin with WeChat Input Method in any
  app and the translation panel appears under the candidates. No installer, no admin rights, and no Python or other
  tools are needed — everything is in this folder.

  This build is not code-signed, so Windows SmartScreen may warn on first launch: choose "More info", then "Run anyway".

FIRST SETUP
  Run Translate.exe again (or press Ctrl+Alt+O) to open Settings.
  Settings > Translation: choose your translation service, paste its API key, press "Test connection", then Save.
  Without a service, common words are still translated by the built-in dictionary (Chinese to English).
  Tip: if you click the panel with the mouse, turn on Settings > Appearance > "Keep the panel clickable".

USE
  Alt+1...9 insert a translation, Alt+Shift+1...9 copy it, Alt+0 hides the panel, Alt+` shows the full text.
  Ctrl+Alt+P pauses or resumes. Quit from the panel's ... menu or Settings > About.

PRIVACY
  Candidates you type are translated only by the service you choose (or not at all in Local-only mode).
  Your API key is kept in Windows Credential Manager. Logs never contain what you type.
  Only short dictionary words are cached on disk (encrypted for your Windows account).

REMOVE
  Quit Translate, delete this folder and %APPDATA%\\Translate. API keys: Windows Credential Manager >
  Windows Credentials > entries starting with "Translate:service:".

Third-party components and licenses: THIRD_PARTY_NOTICES.txt.
"""


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    src = Path(sys.argv[1]).resolve()
    rel = ROOT / "release"
    folder = rel / NAME
    shutil.rmtree(folder, ignore_errors=True)
    rel.mkdir(exist_ok=True)
    shutil.copytree(src, folder)
    (folder / "README-FIRST.txt").write_text(README.replace("\n", "\r\n"), encoding="utf-8")
    zpath = rel / f"{NAME}.zip"
    zpath.unlink(missing_ok=True)
    files = sorted(p for p in folder.rglob("*") if p.is_file())
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in files:
            z.write(p, f"{NAME}/{p.relative_to(folder).as_posix()}")
    exe_hash = sha256(folder / "Translate.exe")
    zip_hash = sha256(zpath)
    (rel / "SHA256SUMS.txt").write_text(f"{zip_hash}  {zpath.name}\r\n{exe_hash}  {NAME}/Translate.exe\r\n", encoding="ascii")
    size = sum(p.stat().st_size for p in files)
    print(json.dumps({"zip": str(zpath), "zip_mb": round(zpath.stat().st_size / 2**20, 1), "unpacked_mb": round(size / 2**20, 1),
                      "files": len(files), "sha256": zip_hash}))


if __name__ == "__main__":
    main()
