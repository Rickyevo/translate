# Release build

## 0.2.4 backend memory reduction

Release: `release/Translate-0.2.4-win-x64.zip` (61.4 MiB; 157.5 MiB unpacked), with `release/SHA256SUMS.txt`.
WeChat Input Method uses the native x64 observer by default; Frida remains an explicit compatibility transport.
The observer uses a 2 MiB ring and at most eight pending dispatch packets. A queue gap invalidates the composition
before insertion, and a fresh composition restores normal operation. Reconnects check process creation time;
stop or five seconds without a heartbeat disables capture and releases the lease. The small DLL stays resident
until the input method exits naturally, with versioned runtime copies avoiding locks on the installation folder.
Microsoft Pinyin keeps the full UI Automation implementation. No interface, shortcut or placement changes.

Verified: TypeScript typecheck; cargo 8/8; backend 82/82; packaged WeChat replay 40/40; Microsoft Pinyin replay 15/15;
clean-environment release check 11/11 (including native observation without Frida). Real candidate reading, dictionary
translations and Alt+1 insertion with both input methods passed before the version bump. Native integration
covered synchronous and asynchronous writes, 256 KiB payloads, queue pressure, bounded dispatch, controller crash,
heartbeat expiry, process replacement, attachment cancellation and concurrent shutdown checks.

The 73-second paired backend comparison measured about 117 MiB → 59 MiB working set during typing and idle,
with no noticeable candidate or translation latency regression. CPU use increased by about 0.7 percentage points
of one core in that short run; this is not a claim of zero overhead or a long-duration stability test.
See [the measurement record](../measurements/native-memory-20261018.md) for scope, timings and raw evidence.

## 0.2.3 Settings refresh and custom shortcuts

Release: `release/Translate-0.2.3-win-x64.zip` (61.2 MB; 157.2 MB unpacked).
Pause, Open Settings and Hide or show the panel are recordable in General. While a shortcut is being recorded the host
releases all of Translate's global shortcuts (`shortcuts:record`), and a candidate combination is test-registered
(`shortcut:check`) before it goes into the draft. The host reports shortcuts Windows refused (another app holds them)
and pushes them, with the input-method states, to Settings on change (`status` event); Settings no longer polls.
Overview combines status, service, target language, per-input-method state and switches, and the everyday shortcuts;
About links to updates, issues and third-party licenses through fixed host destinations (`link:open`).
`TRANSLATE_NO_HOTKEYS` (test control only) keeps screenshot runs from registering shortcuts.

Verified: TypeScript typecheck; cargo 8/8; backend 76/76; shortcuts 25/25 (refusals, another app holding a key,
save and the action it runs, off, reset, single recorder, live warning and its clearing); Microsoft Pinyin replay 15/15;
Overview 4/4; replay 40/40; service 19/19; autostart 8/8; placement 35/35; Settings UI 11/11; clean-environment
release check 10/10.

## 0.2.2 connection display

Release: `release/Translate-0.2.2-win-x64.zip` (about 61.2 MB; 157.2 MB unpacked).
Overview and About both list WeChat Input Method and Microsoft Pinyin with independent connection indicators.
The host now retains the backend's full adapter-state map and clears it on backend exit. Settings refreshes the
connection indicators every two seconds, and mode changes report removed adapters as no longer connected.
Connected means the adapter is ready; it does not mean Windows currently has that input method selected.

Verified: TypeScript typecheck; backend 76/76; packaged Microsoft Pinyin replay 15/15 (including independent
disconnect/reconnect transitions on Overview and About); Overview card 4/4; clean-environment checks 10/10.

## 0.2.1 hotfix

Release: `release/Translate-0.2.1-win-x64.zip` with `release/SHA256SUMS.txt`.
Microsoft Pinyin's generated COM wrappers in 0.2.0 could fail their system-DLL timestamp check with
`ImportError: Typelib different than module`. The observer now uses comtypes' typelib loader, reusing compatible
wrappers or regenerating them in memory for the local Windows installation. No system or installation files are modified.

Regression coverage forces stale timestamps in copied wrappers and initializes UI Automation in a separate process,
checking that the copied installation remains unchanged. The clean-environment release check now tests Microsoft Pinyin's
UI Automation initialization independently; a connected WeChat adapter alone is insufficient.

Verified: backend tests 75/75; TypeScript typecheck; bundled-runtime clean-environment checks 10/10;
packaged Microsoft Pinyin replay checks 12/12 (including automatic takeover from WeChat Input Method).
No keyboard/mouse-controlled live session was run for this hotfix; actual typing on other PCs remains unverified.
Package size: about 61.2 MB downloaded and 157.2 MB unpacked.

## 0.2.0 verification record

Portable Windows x64 release: `release/Translate-0.2.0-win-x64.zip` (61 MB; 156 MB unpacked, 80 files) and
`release/SHA256SUMS.txt`. Unzip anywhere and run `Translate.exe` — no installer, no admin rights, no Python, Node or
other development tools. The interface runs in the Microsoft Edge WebView2 Runtime that is part of Windows (if it is
missing, Translate says so and offers the download page). Not code-signed (SmartScreen warns on first launch). User
notes: `README-FIRST.txt` in the zip.

## What is bundled

| Part | Where | Notes |
|---|---|---|
| Tauri 2 host | `Translate.exe` (≈ 4 MB) | Rust; the UI (`app/dist/renderer`) is embedded; WebView2 with software rendering, DevTools only with `--test-control` |
| Python 3.12.9 runtime | `resources/python/` (19 MB) | `TranslateEngine.exe` + DLLs + stdlib as precompiled `python312.zip`; isolated by `python312._pth` (ignores PYTHONPATH/PYTHONHOME, user site and any installed Python). Built from the local CPython by `app/scripts/bundle_python.py` |
| Backend | `resources/backend/` | precompiled; Frida 17.23.3 in `vendor/` (129 MB, most of the size); CC-CEDICT data |
| Licenses | `LICENSE.txt` (Translate, MIT), `THIRD_PARTY_NOTICES.txt`, `THIRD_PARTY_RUST.txt` (every Rust crate in the exe, with license texts), `resources/python/LICENSE.txt`, `cedict.LICENSE` | |

## Build

```
cd app
python -X utf8 scripts/package.py                 # renderer, host (cargo), engine + Python runtime → release-build/
python -X utf8 scripts/make_release.py release-build/Translate-win32-x64
```

Needs Node, CPython 3.12 (bundled from it) and Rust (MSVC) on PATH. `make_release.py` builds the zip from a staging
copy in `.cache/release-stage/` and refreshes the unpacked `release/Translate-<version>-win-x64/` only when no running
Translate uses it.

## Verification of 0.2.0 (on the release, copied out of the source tree; release check in an environment with only Windows folders on PATH and no PYTHON*/NODE* variables)

| Check | Result |
|---|---|
| `release_verify.py` on the folder extracted from the zip | 9 / 9 — bundled `TranslateEngine.exe`; 0 of 90 mapped files from outside the release; IME attached in 1.4 s; no visible windows; clean exit, no leftovers |
| Visual parity with 0.1.1 (`parity_shots.py`) | 28 / 28 captures pixel-identical: panel, lead preview, Overview, General, Translation, Appearance, Privacy — light and dark |
| Placement geometry (`cargo test`) | 9 screens (1366×768 … 3840×2160, 100–200 %, negative-origin monitors) × 5 bar layouts × 13 heights × 3 horizontal positions × caret above/below, reported or not × default/clickable: never over the bar or typing line, always inside the work area; the reported bottom-edge case; mutation check (no line clearance) fails both tests |
| Placement in the app (`placement_test.py`) | 35 / 35 |
| LIVE, real WeType + real typing (`live_edge_test.py`) | Win32 text box (system caret): middle, top edge, bottom edge, bottom-right corner, very bottom — 20 / 20, incl. WeType's bar flipped above the caret; Edge text area (accessibility caret): 22 / 22 after the window-blink fix (before: candidates missing in 2–4 of 5 cases), with the caret lookup off as well (line-height fallback) — candidates every time, typing line clear. `measurements/stage6/live-edge-*.json` |
| Stage-4 replay suite | 40 / 40 (incl. lead preview via `window.open`, idle release and recreation, engine restart) |
| Translation pipeline vs local mock | 19 / 19 |
| Start with Windows + footer | 8 / 8 |
| Overview service card | 4 / 4 |
| Settings UI (dropdowns, scrollbars) | 11 / 11 |
| Backend unit tests | 64 / 64 |
| Memory (private, whole process tree; replay) | idle before the first list 16 MB (0.1.1: 74), panel + preview shown 146 MB (123), after the idle release 20 MB (83) |

## 0.2.0

- **Host**: Electron replaced by Tauri 2 + WebView2 (`app/src-tauri/`); the renderer and the engine are unchanged. The
  pages get the same `window.translate` API from `bridge.js`. The preview is still opened by the panel page with
  `window.open` into a window of the same WebView2 environment, so it shares the panel's renderer. Click-through is a
  window region (only the drawn panel takes the mouse) instead of Electron's forwarded mouse events.
- **Placement**: also clear of the typing line when the panel goes above WeType's bar (DESIGN §9 "Screen edges"); the
  engine passes the app's caret (system caret, else MSAA `OBJID_CARET`) with the bar.
- **Overview**: one *Connect a translation service* card instead of the three-step checklist.
- Settings without a native frame: Tauri's size bookkeeping for frameless resizable windows is off by the caption
  height, so the page reports its viewport and the host sizes the window to give exactly 860 × 620.

## Earlier releases

## 0.1.1

Compatibility fixes after testing on a second PC (overlap and see-through text in the panel):

- **Bar detection**: the engine finds WeType's bar where it is drawn (its candidate window rendered alone into memory,
  box of drawn pixels; DESIGN §9 "Finding the bar") instead of fixed 109/70 px offsets measured on one layout at 96 dpi.
  On this PC the bar is actually at 136/43 in WeType 3.0.0.34; the old offsets only matched its bottom edge.
  `test_bar_detection.py` (both layouts, flipped bars, dark skin, 100–200 % scaling, fallbacks) and
  `placement_test.py` 35 / 35 (middle, edges, flips, clickable mode).
- **Opacity**: opaque by default, 90–100 %; saved 97 % migrates to 100 %, lower values to 90 %. Verified in the
  packaged Settings for 0.97 / 0.7 / 0.95 / unset.
- **Settings window**: fits the screen it opens on (≤ 860 × 620 DIP), resizable, minimum 720 × 440.
- Regression on the 0.1.1 build: backend 64 / 64, replay 40 / 40, service 19 / 19, Start with Windows 8 / 8, setup
  checklist 6 / 6, settings UI 11 / 11, release in a clean environment 9 / 9.

## 0.1.0

First public release; earlier builds were internal development builds numbered up to 0.6.1 (history below).

- **Start with Windows works**: a per-user Run entry for this `Translate.exe`, written at every start and on Save,
  removed when the setting is off. Test and verification runs (isolated profile) never touch it.
- **Panel footer**: the ⋯ menu and the target-language dropdown are removed; the language pair is plain text.
  Pause/Hide/Settings/Quit remain on Ctrl+Alt+P, Alt+0, Ctrl+Alt+O and Settings › About.
- **Setup checklist**: step 3 ("Type pinyin in any app") was hard-coded as not done. Main now records the first time
  the visible panel shows a real (not simulated) translation in `progress.json` (separate from `config.json`, so a
  settings save can't reset it), tells an open Settings window, and reports it at every start.
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
