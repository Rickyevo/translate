"""Make the distributable: release/Translate-<version>-win-x64.zip (+ SHA256SUMS.txt) from a packaged build.

The zip holds one folder, Translate-<version>-win-x64/, with Translate.exe, the bundled Python runtime and backend,
Translate's license (LICENSE.txt), third-party notices (THIRD_PARTY_NOTICES.txt, THIRD_PARTY_RUST.txt) and
README-FIRST.txt.
The zip is built from a staging copy in .cache/; release/<name>/ is refreshed only when no running Translate uses it. Portable: unzip anywhere and run; no installer, no admin rights, no Python or
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
VERSION = json.loads((ROOT / "app" / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))["version"]
NAME = f"Translate-{VERSION}-win-x64"

README = f"""Translate {VERSION} — translation companion for WeChat Input Method (Windows 10/11, x64)

START
  Unzip this folder anywhere you like (for example %LOCALAPPDATA%\\Programs\\Translate) and run Translate.exe.
  Nothing appears at first: Translate runs quietly in the background. Type pinyin with WeChat Input Method in any
  app and the translation panel appears under the candidates. No installer, no admin rights, and no Python or other
  tools are needed — everything is in this folder; the interface uses the WebView2 Runtime built into Windows.

  This build is not code-signed, so Windows SmartScreen may warn on first launch: choose "More info", then "Run anyway".

FIRST SETUP
  Run Translate.exe again (or press Ctrl+Alt+O) to open Settings.
  Settings > Translation: choose your translation service, paste its API key, press "Test connection", then Save.
  Without a service, common words are still translated by the built-in dictionary (Chinese to English).
  Tip: if you click the panel with the mouse, turn on Settings > Appearance > "Keep the panel clickable".

USE
  Alt+1...9 insert a translation, Alt+Shift+1...9 copy it, Alt+0 hides the panel, Alt+` shows the full text.
  Ctrl+Alt+P pauses or resumes. Right-click a row to insert, copy or retry. Quit from Settings > About.

PRIVACY
  Candidates you type are translated only by the service you choose (or not at all in Local-only mode).
  Your API key is kept in Windows Credential Manager. Logs never contain what you type.
  Only short dictionary words are cached on disk (encrypted for your Windows account).

START WITH WINDOWS
  After its first run, Translate starts with Windows from this folder (Settings > General > Start with Windows).
  If you move the folder, run Translate.exe once from the new place.

REMOVE
  Turn off Settings > General > Start with Windows and Save, quit Translate (Settings > About), then delete this
  folder and %APPDATA%\\Translate. API keys: Windows Credential Manager > Windows Credentials > entries starting
  with "Translate:service:".

Translate is an independent project, not made by, affiliated with or endorsed by Tencent or WeChat.
It is tested with WeChat Input Method 3.0.0.34; other versions may not work.

License: LICENSE.txt (MIT). Third-party components and licenses: THIRD_PARTY_NOTICES.txt.
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
    stage = ROOT / ".cache" / "release-stage" / NAME
    shutil.rmtree(stage.parent, ignore_errors=True)
    shutil.copytree(src, stage)
    shutil.copyfile(ROOT / "LICENSE", stage / "LICENSE.txt")
    shutil.copyfile(ROOT / "app" / "build" / "THIRD_PARTY_NOTICES.txt", stage / "THIRD_PARTY_NOTICES.txt")
    (stage / "README-FIRST.txt").write_text(README, encoding="utf-8", newline=chr(13) + chr(10))
    rel.mkdir(exist_ok=True)
    zpath = rel / f"{NAME}.zip"
    zpath.unlink(missing_ok=True)
    files = sorted(p for p in stage.rglob("*") if p.is_file())
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in files:
            z.write(p, f"{NAME}/{p.relative_to(stage).as_posix()}")
    exe_hash = sha256(stage / "Translate.exe")
    zip_hash = sha256(zpath)
    (rel / "SHA256SUMS.txt").write_text(f"{zip_hash}  {zpath.name}\r\n{exe_hash}  {NAME}/Translate.exe\r\n", encoding="ascii", newline="")
    size = sum(p.stat().st_size for p in files)
    # The unpacked copy in release/: never delete one someone is running (Windows lets most of its files be removed
    # underneath it). Then the zip is still complete; only the unpacked copy stays as it was.
    folder = rel / NAME
    import psutil
    busy = [p.info["pid"] for p in psutil.process_iter(["pid", "exe"]) if p.info["exe"] and str(folder).lower() in p.info["exe"].lower()]
    if busy:
        print(f"note: {folder} is in use by running processes {busy}; left as it was (the zip is up to date)")
    else:
        shutil.rmtree(folder, ignore_errors=True)
        shutil.copytree(stage, folder)
    print(json.dumps({"zip": str(zpath), "zip_mb": round(zpath.stat().st_size / 2**20, 1), "unpacked_mb": round(size / 2**20, 1),
                      "files": len(files), "sha256": zip_hash}))


if __name__ == "__main__":
    main()
