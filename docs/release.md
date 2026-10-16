# Release build (0.1.0)

Portable Windows x64 release: `release/Translate-0.1.0-win-x64.zip` (198 MB; 474 MB unpacked, 100 files) and
`release/SHA256SUMS.txt`. Unzip anywhere and run `Translate.exe` — no installer, no admin rights, no Python, Node or
other development tools. Not code-signed (SmartScreen warns on first launch). User notes: `README-FIRST.txt` in the zip.

## What is bundled

| Part | Where | Notes |
|---|---|---|
| Electron 44 app | `Translate.exe`, `resources/app.asar` | asar integrity, hardened fuses, 4 UI locales |
| Python 3.12.9 runtime | `resources/python/` (19 MB) | `TranslateEngine.exe` + DLLs + stdlib as precompiled `python312.zip`; isolated by `python312._pth` (ignores PYTHONPATH/PYTHONHOME, user site and any installed Python). Built from the local CPython by `app/scripts/bundle_python.py` |
| Backend | `resources/backend/` | precompiled; Frida 17.23.3 in `vendor/`; CC-CEDICT data |
| Licenses | `LICENSE.txt` (Translate, MIT), `THIRD_PARTY_NOTICES.txt`, `LICENSE.electron.txt`, `LICENSES.chromium.html`, `resources/python/LICENSE.txt`, `cedict.LICENSE` | |

## Build

```
cd app
npm run build
node scripts/package.mjs --out=release-build      # needs CPython 3.12 on PATH (bundled from it)
python -X utf8 scripts/make_release.py release-build/Translate-win32-x64
```

`make_release.py` builds the zip from a staging copy in `.cache/release-stage/` and refreshes the unpacked
`release/Translate-<version>-win-x64/` only when no running Translate uses it.

## Verification of 0.1.0 (on the release, copied out of the source tree, in an environment with only Windows folders on PATH and no PYTHON*/NODE* variables)

| Check | Result |
|---|---|
| `release_verify.py` on the folder extracted from the zip | 9 / 9 — backend is the bundled `TranslateEngine.exe`; 0 of 81 mapped files from outside the release; Frida, OpenSSL, ctypes load from the release; IME attached in 1.6 s; no visible windows; clean exit, no leftovers |
| Start with Windows and panel footer (`autostart_test.py`) | 8 / 8 — Run entry added at start and on Save, removed when turned off; footer has no buttons or menus; version 0.1.0; nothing left behind |
| Stage-4 replay suite | 40 / 40 |
| Translation pipeline vs local mock | 19 / 19 |
| Settings UI (dropdowns, scrollbars) | 11 / 11 |
| README captures with the real service (`readme_shots.py`) | language pair shown as plain text |
| Backend unit tests | 59 / 59 |
| Real service accuracy and speed (development build 0.5.2) | 15 / 15, p50 1.65 s |
| Zip contents | no settings, caches, logs, keys or personal paths; `SHA256SUMS.txt` checks with `sha256sum -c` |

## 0.1.0

First public release; earlier builds were internal development builds numbered up to 0.6.1 (history below).

- **Start with Windows works**: a per-user Run entry for this `Translate.exe`, written at every start and on Save,
  removed when the setting is off. Test and verification runs (isolated profile) never touch it.
- **Panel footer**: the ⋯ menu and the target-language dropdown are removed; the language pair is plain text.
  Pause/Hide/Settings/Quit remain on Ctrl+Alt+P, Alt+0, Ctrl+Alt+O and Settings › About.
- Settings › Overview: "Run Translate.exe again" instead of a Start menu entry the portable release doesn't have; the
  menu row is replaced by the hide shortcut and where to quit.
- Version 0.1.0 in the app, package metadata, backend, docs and release files; MIT license in package metadata and the
  exe's copyright field.

## Development build history

### 0.6.1

- Release zip: Translate's own license (`LICENSE.txt`, MIT), Electron's renamed to `LICENSE.electron.txt`;
  README-FIRST gains a disclaimer, the tested WeType version and a start-with-Windows workaround. `SHA256SUMS.txt`
  and README-FIRST had doubled carriage returns (CR CR LF), which broke `sha256sum -c`; fixed. Verified again from the
  extracted zip in a clean environment: 9 / 9.

- **Floating panel and lead preview are flat**: no drop shadow, a 1 px border only (`--sh-bar`), per your request;
  Settings unchanged. `screenshots/stage5/panel-border-only.png` (in-app capture, light and dark).
- Verified: release extracted from the zip, clean environment 9 / 9; stage-4 replay 40 / 40; panel menu 7 / 7;
  0 blink frames; 1 window resize while typing.

### 0.6.0 fixes (reported during release)

- **Pause control reversed** — the Overview switch was "Pause translation" (on = paused, lit while paused). Now
  "Translate while typing": lit while translating, dimmed when paused. The settings window also didn't follow
  pausing done elsewhere (panel ⋯, Ctrl+Alt+P) and showed a stale state; it now updates live. Verified both ways.
- **Text field shadow** — fields used the card's fill and no contact shadow, unlike the Select/Button next to them
  (flat in light, nearly invisible in dark). They now use the same control recipe. Before/after:
  `screenshots/stage5/fields/fields-{before,after}.png`.
- **Flicker while typing** — the panel window was resized on most keystrokes (10 resizes in 8 keystrokes) as rows
  appeared or translations got longer; each resize could show a stale/blank frame. The window is now sized to the
  panel's capacity and only the content changes inside it: 1 resize (the lead preview opening). Placeholder flips 0,
  blink frames 0.

## Not covered

Code signing; an installer (MSI/MSIX) and auto-update; other Windows machines/VMs (verified on this PC with a
stripped environment, not on a machine that never had Python); multi-monitor and DPI scaling; Edge/Word/WeChat as
targets; multi-hour soak; Start with Windows at a real sign-in (the Run entry is verified, a reboot was not done).
