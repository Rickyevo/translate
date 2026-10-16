# Development

How the project is laid out, how to build it from a fresh clone, and how it is tested. For using the app, see the
[README](../README.md); for how the release is packaged, see [release.md](release.md).

## Layout

| Path | Contents |
|---|---|
| `app/src-tauri/` | Tauri 2 / WebView2 host (Rust): `host.rs` (state, lists, windows, placement, Settings, test control), `layout.rs` (panel and preview placement, unit-tested), `backend.rs` (engine process), `system.rs` (shortcuts, single instance, theme), `win.rs` (Win32), `bridge.js` (the pages' `window.translate`) |
| `app/src/renderer/` | The panel and Settings pages (React; the UI itself lives in `prototype/src`) |
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

Not in the repository (see `.gitignore`): `node_modules/`, build output (`app/dist`, `app/src-tauri/target`, `release/`), local
caches (`.cache/`) and the vendored Frida runtime — its `_frida.pyd` is 129 MB, over GitHub's file limit.

Requirements: Windows 10/11 x64, Node 22+, Python 3.12 on PATH (or set `TRANSLATE_PYTHON`), Rust (stable, MSVC target)
with the Visual Studio Build Tools, and WeChat Input Method for anything beyond the replay tests.

```
python -m pip install --target backend/vendor frida==17.23.3   # the WeType adapter's Frida dependency
cd app && npm install && cd ..
cd prototype && npm install && cd ..
```

Translation-service keys are never stored in the repository or in config files: each user enters theirs in
Settings › Translation and it goes to Windows Credential Manager.

## Build and run

```
cd app
npm run build                           # defaults.json, renderer (Vite), host (cargo build --release)
src-tauri\target\release\Translate.exe  # run (engine from ../backend with the Python on PATH)
python -X utf8 scripts/package.py       # production package → app/release-build/Translate-win32-x64/
cd src-tauri && cargo test --release     # placement geometry, settings, shortcuts
```

The portable release (bundled Python runtime, zip, checksums) is described in [release.md](release.md).

## Tests and measurements

Run from `app/`. Scripts marked LIVE use the real WeChat Input Method and send real keystrokes or clicks: don't touch
the PC while they run.

```
python -X utf8 -m unittest discover -s ../backend/tests                   # backend incl. bar detection, no IME, no input
python -X utf8 scripts/stage4_replay_test.py [--packaged]                 # real adapter path, synthetic bytes, no input
python -X utf8 scripts/stage5_service_test.py [--packaged]                # translation pipeline vs a local mock service
python -X utf8 scripts/stage5_real_test.py                                # your configured service, sample texts, no input
python -X utf8 scripts/placement_test.py                                  # panel vs WeType's bar and canvas, edges (packaged)
python -X utf8 scripts/overview_card_test.py                              # Overview's service card (packaged)
python -X utf8 scripts/parity_shots.py <reference exe> <candidate exe>    # pixel parity of two host builds
python -X utf8 scripts/live_placement_probe.py <Translate.exe> [seconds]   # LIVE, read-only: you type; checks placement
python -X utf8 scripts/live_edge_test.py [Translate.exe] [--edge-only]     # LIVE: types into its own Tk/Edge windows at screen edges
python -X utf8 scripts/autostart_test.py                                   # Start with Windows + panel footer (packaged)
python -X utf8 scripts/settings_ui_probe.py                               # settings dropdowns and scrollbars
python -X utf8 scripts/release_verify.py <release folder>                 # release in an environment without dev tools
python -X utf8 scripts/stage4_live_test.py [--clickable] [--edge]         # LIVE: real WeType + real keys/clicks
python -X utf8 scripts/readme_shots.py                                    # README screenshots (DevTools captures)
python -I ../backend/tools/build_cedict.py <cedict_1_0_ts_utf-8_mdbg.zip> # rebuild the local dictionary
```

Test runs use an isolated profile in `.cache/test-userdata`, never your `%APPDATA%\Translate`. Screenshots are taken
from the pages themselves (DevTools, enabled only together with `--test-control`), never of the desktop.

`TRANSLATE_DIAG=1` makes the engine log counts (never content) of what the WeType adapter receives and drops, once a
second; `TRANSLATE_NO_A11Y_CARET=1` turns off the accessibility-caret lookup.

Electron-era measurement scripts (`measure.py`, `measure_report.py`, `measure_stage4.py`, `focus_test.py`) are kept for
the stage-3/4 reports; they assume Electron's process layout.

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
