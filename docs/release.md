# Release build (0.6.0)

Portable Windows x64 release: `release/Translate-0.6.0-win-x64.zip` (198 MB; 474 MB unpacked, 99 files) and
`release/SHA256SUMS.txt`. Unzip anywhere and run `Translate.exe` — no installer, no admin rights, no Python, Node or
other development tools. Not code-signed (SmartScreen warns on first launch). User notes: `README-FIRST.txt` in the zip.

## What is bundled

| Part | Where | Notes |
|---|---|---|
| Electron 44 app | `Translate.exe`, `resources/app.asar` | asar integrity, hardened fuses, 4 UI locales |
| Python 3.12.9 runtime | `resources/python/` (19 MB) | `TranslateEngine.exe` + DLLs + stdlib as precompiled `python312.zip`; isolated by `python312._pth` (ignores PYTHONPATH/PYTHONHOME, user site and any installed Python). Built from the local CPython by `app/scripts/bundle_python.py` |
| Backend | `resources/backend/` | precompiled; Frida 17.23.3 in `vendor/`; CC-CEDICT data |
| Licenses | `THIRD_PARTY_NOTICES.txt`, `LICENSE`, `LICENSES.chromium.html`, `resources/python/LICENSE.txt`, `cedict.LICENSE` | |

## Build

```
cd app
npm run build
node scripts/package.mjs --out=release-build      # needs CPython 3.12 on PATH (bundled from it)
python -X utf8 scripts/make_release.py release-build/Translate-win32-x64
```

## Verification (all on the release, copied out of the source tree, in an environment with only Windows folders on PATH and no PYTHON*/NODE* variables)

| Check | Result |
|---|---|
| `release_verify.py` on the folder extracted from the zip | 9 / 9 — backend is the bundled `TranslateEngine.exe`; 0 of 81 mapped files from outside the release; Frida, OpenSSL, ctypes load from the release; IME attached in 1.5 s; no visible windows; clean exit, no leftovers |
| Stage-4 replay suite | 40 / 40 |
| Translation pipeline vs local mock | 19 / 19 |
| Panel ⋯ menu | 7 / 7 |
| Settings UI (dropdowns, scrollbars) | 11 / 11 |
| Real service (OpenCode Go, your key; on 0.5.2 + bundled runtime) | 15 / 15, p50 1.65 s |
| Backend unit tests | 59 / 59 |

## 0.6.0 fixes (reported during release)

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
targets; multi-hour soak.
