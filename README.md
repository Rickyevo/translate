# Translate

A Windows companion for WeChat Input Method. It translates the IME's Chinese candidates into your chosen
language in a small floating panel, and inserts the translation you pick (click or Alt+1…9).

**Current stage: 5 — real translation.** The packaged app reads WeChat Input Method (WeType) candidates
locally and translates them: translation cache → local CC-CEDICT dictionary (Chinese → English words) → a
translation service you choose (OpenAI, Claude, Gemini, Grok, OpenCode Go, DeepSeek or a custom
OpenAI/Claude/Gemini-compatible endpoint). Keys are stored in Windows Credential Manager. See
`docs/stage5-report.md`.

## Layout

| Path | Contents |
|---|---|
| `DESIGN.md` | Design system: principles, tokens, components, bar spec, settings model, tray-free model |
| `docs/lead-preview-report.md` | Lead preview (long translations) + final icon: placements, verification |
| `docs/stage2-report.md` | Panel refinements (before/after), icon research + concepts, verification |
| `docs/stage1-report.md` | Stage 1: two directions, rationale, verification |
| `docs/archive/` | Stage-1 prototype source (incl. removed direction A) |
| `assets/icons/app/` | Final app icon (Overlap): `translate.ico`, PNG/SVG, monochrome glyphs |
| `assets/icons/concepts/` | All four icon concepts (reference) |
| `docs/research/` | Linear articles (saved), images and study notes |
| `app/` | Electron 44 app: `src/main` (windows, hotkeys, backend supervisor), `src/preload`, `src/renderer` (panel, settings) |
| `app/scripts/` | Build/package, real-desktop focus test, resource measurement + report |
| `backend/` | Python backend (stdlib + ctypes + vendored Frida): protocol, WeType adapter (`translate_backend/wetype/`), Win32 input and window events, simulated translations, fixture source; `tests/` (no IME, no input); `tools/` research capture tools (dev only, not packaged) |
| `docs/protocol.md` | Host ↔ backend JSON Lines protocol |
| `docs/stage5-report.md` | Stage 5: translation service, dictionary, hybrid cache, keys, verification, resources |
| `docs/stage4-report.md` | Stage 4: real candidates, composition handling, verification, before/after resources |
| `docs/stage3-report.md` | Stage 3: architecture, focus verification, resource measurements, recommendation |
| `measurements/stage3/`, `measurements/stage4/` | Raw samples, summaries, charts; stage-4 replay/live results (counts and timings only) |
| `prototype/` | Design lab + shared UI source (the app imports components from `prototype/src`) |
| `prototype/src/styles/tokens.css` | All design tokens (both directions, both themes) |
| `prototype/src/i18n/locales/` | zh-CN, en, ja, ko catalogs |
| `prototype/scripts/` | Screenshot, interaction-check and comparison scripts (system Edge via playwright-core) |
| `screenshots/stage2/` | Current renders, before/after sheets, icon sheet, interaction captures |
| `screenshots/stage1/` | Stage-1 renders and A/B comparison sheets |
| `.cache/` | Project-local npm and Vite caches |

## From a fresh clone

Not in the repository (see `.gitignore`): `node_modules/`, build output (`app/dist`, `app/out`), local caches (`.cache/`)
and the vendored Frida runtime — its `_frida.pyd` is 129 MB, over GitHub's file limit. Restore them with:

```
python -m pip install --target backend/vendor frida==17.23.3   # the WeType adapter's Frida dependency
cd app && npm install && node node_modules/electron/install.js && cd ..
cd prototype && npm install && cd ..
```

Translation-service keys are never stored in the repository or in config files: each user enters theirs in
Settings › Translation and it goes to Windows Credential Manager.

## Build and run the app

Requirements: Windows 10/11 x64, Node 22+, Python 3.12 on PATH (or set `TRANSLATE_PYTHON`).

```
cd app
npm install
node node_modules/electron/install.js   # once: npm's script policy skips Electron's binary download
npm run build                           # main + preload (esbuild) and renderer (Vite)
npm start                               # dev run (unpackaged)
node scripts/package.mjs                # production package → app/out/Translate-win32-x64/Translate.exe
```

Tests and measurements (run from `app/`):

```
python -X utf8 -m unittest discover -s ../backend/tests                   # backend, no IME, no input
python -X utf8 scripts/stage4_replay_test.py [--packaged]                 # real adapter path, synthetic bytes, no input
python -X utf8 scripts/measure_stage4.py --label NAME [--quick]           # live idle + replay typing resources
python -X utf8 scripts/stage4_live_test.py [--clickable] [--edge]         # LIVE: real WeType + real keys/clicks — ask first
python -X utf8 scripts/stage5_service_test.py [--packaged]                # translation pipeline vs a local mock service
python -I ../backend/tools/build_cedict.py <cedict_1_0_ts_utf-8_mdbg.zip>   # rebuild the local dictionary
python -X utf8 scripts/focus_test.py [--packaged] [--only tk|edge]   # real mouse/keyboard input — don't touch the PC for ~3 min
python -X utf8 scripts/measure.py --variant default --sustained-min 20
python -X utf8 scripts/measure_report.py
```

## Run the prototype

```
cd prototype
npm install
npm run dev          # http://localhost:5320
npm run typecheck
npm run shots        # regenerate screenshots/stage2 (needs Microsoft Edge installed)
node scripts/interact.mjs
node scripts/test_place.mjs   # placement geometry
node scripts/lead_shots.mjs   # lead-preview placement screenshots
node scripts/export_icons.mjs && python scripts/build_ico.py
```
