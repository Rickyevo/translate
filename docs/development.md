# Development

How the project is laid out, how to build it from a fresh clone, and how it is tested. For using the app, see the
[README](../README.md); for how the release is packaged, see [release.md](release.md).

## Layout

| Path | Contents |
|---|---|
| `app/` | Electron 44 app: `src/main` (windows, hotkeys, backend supervisor), `src/preload`, `src/renderer` (panel, settings) |
| `app/scripts/` | Build, packaging and release scripts; test suites, probes and resource measurements |
| `app/build/THIRD_PARTY_NOTICES.txt` | License notices shipped with the release |
| `backend/` | Python backend (stdlib + ctypes + vendored Frida): protocol, WeType adapter (`translate_backend/wetype/`), Win32 input and window events, translation pipeline (`translate/`), CC-CEDICT data; `tests/` (no IME, no input); `tools/` research and capture tools (development only, not packaged) |
| `prototype/` | Design lab and the shared UI source (the app imports components from `prototype/src`) |
| `prototype/src/styles/tokens.css` | Design tokens (both themes) |
| `prototype/src/i18n/locales/` | zh-CN, en, ja, ko catalogs |
| `prototype/scripts/` | Screenshot, interaction-check and comparison scripts (system Edge via playwright-core) |
| `assets/icons/app/` | App icon (Overlap): `translate.ico`, PNG/SVG, monochrome glyphs |
| `assets/icons/concepts/` | All four icon concepts (reference) |
| `DESIGN.md` | Design system: principles, tokens, components, panel spec, settings model, tray-free model |
| `docs/protocol.md` | Host ↔ backend JSON Lines protocol |
| `docs/privacy.md` | What is read, sent, stored and logged |
| `docs/stage1-report.md` … `docs/stage5-report.md`, `docs/lead-preview-report.md` | Development reports per stage: decisions, verification, measurements |
| `docs/research/` | Design study notes (links to the sources) |
| `docs/archive/` | Stage-1 prototype source (incl. the removed direction A) |
| `measurements/` | Raw samples and summaries (counts and timings; sample texts only, never real typing) |
| `screenshots/readme/` | README and release screenshots (`app/scripts/readme_shots.py`) |
| `screenshots/stage1/`, `stage2/`, `stage5/` | Design-stage renders, before/after sheets, interaction captures |

## From a fresh clone

Not in the repository (see `.gitignore`): `node_modules/`, build output (`app/dist`, `app/out`, `release/`), local
caches (`.cache/`) and the vendored Frida runtime — its `_frida.pyd` is 129 MB, over GitHub's file limit.

Requirements: Windows 10/11 x64, Node 22+, Python 3.12 on PATH (or set `TRANSLATE_PYTHON`), and WeChat Input Method
for anything beyond the replay tests.

```
python -m pip install --target backend/vendor frida==17.23.3   # the WeType adapter's Frida dependency
cd app && npm install && node node_modules/electron/install.js && cd ..
cd prototype && npm install && cd ..
```

`node node_modules/electron/install.js` is needed once because the project's npm settings skip install scripts, which
includes Electron's binary download.

Translation-service keys are never stored in the repository or in config files: each user enters theirs in
Settings › Translation and it goes to Windows Credential Manager.

## Build and run

```
cd app
npm run build                           # main + preload (esbuild) and renderer (Vite)
npm start                               # dev run (unpackaged; uses the Python on PATH)
node scripts/package.mjs                # production package → app/out/Translate-win32-x64/Translate.exe
```

The portable release (bundled Python runtime, zip, checksums) is described in [release.md](release.md).

## Tests and measurements

Run from `app/`. Scripts marked LIVE use the real WeChat Input Method and send real keystrokes or clicks: don't touch
the PC while they run.

```
python -X utf8 -m unittest discover -s ../backend/tests                   # backend, no IME, no input
python -X utf8 scripts/stage4_replay_test.py [--packaged]                 # real adapter path, synthetic bytes, no input
python -X utf8 scripts/stage5_service_test.py [--packaged]                # translation pipeline vs a local mock service
python -X utf8 scripts/stage5_real_test.py                                # your configured service, sample texts, no input
python -X utf8 scripts/panel_menu_probe.py                                # panel ⋯ menu
python -X utf8 scripts/settings_ui_probe.py                               # settings dropdowns and scrollbars
python -X utf8 scripts/release_verify.py <release folder>                 # release in an environment without dev tools
python -X utf8 scripts/stage4_live_test.py [--clickable] [--edge]         # LIVE: real WeType + real keys/clicks
python -X utf8 scripts/focus_test.py [--packaged] [--only tk|edge]        # LIVE: real mouse/keyboard input, ~3 min
python -X utf8 scripts/measure_stage4.py --label NAME [--quick]           # live idle + replay typing resources
python -X utf8 scripts/readme_shots.py                                    # README screenshots (in-app captures)
python -I ../backend/tools/build_cedict.py <cedict_1_0_ts_utf-8_mdbg.zip> # rebuild the local dictionary
```

Test runs use an isolated profile in `.cache/test-userdata`, never your `%APPDATA%\Translate`. Screenshots are taken
with the app's own window capture, never of the desktop.

## Prototype

```
cd prototype
npm run dev          # http://localhost:5320
npm run typecheck
npm run shots        # regenerate screenshots/stage2 (needs Microsoft Edge)
node scripts/interact.mjs
node scripts/test_place.mjs   # placement geometry
node scripts/lead_shots.mjs   # lead-preview placement screenshots
node scripts/export_icons.mjs && python scripts/build_ico.py
```
