# Changelog

## 0.6.1 — 2026-10-16

First public release.

- The floating panel and the full-text preview are flat: a thin border instead of a drop shadow.
- The release zip now includes Translate's own license (`LICENSE.txt`); Electron's is `LICENSE.electron.txt`.

## 0.6.0 — 2026-10-16

- Portable release: Python runtime and all dependencies bundled; runs without Python, Node or other tools installed.
- The pause switch is now "Translate while typing": on while translating, off when paused, and it follows pausing
  done from the panel or with Ctrl+Alt+P.
- Text fields in Settings match the other controls.
- No more flicker while typing: the panel window keeps its size and only its content changes.

## 0.5.x — development builds

- Real translation services: OpenAI, Claude, Gemini, Grok, OpenCode Go, DeepSeek and custom endpoints, with
  configurable model, endpoint and authentication; keys in Windows Credential Manager.
- Built-in CC-CEDICT dictionary for instant Chinese → English words; hybrid cache (words on disk, encrypted;
  everything else in memory only).
- One batched request per candidate list, short debounce while typing, a second request if the service stalls, and
  reasoning turned off for speed.
- Translations still loading keep the previous text, dimmed, instead of flashing placeholders.
- The panel's ⋯ menu opens reliably.

## 0.4 and earlier — development builds

- Real WeChat Input Method candidates and pinyin composition; insertion by Alt+1…9 or click without taking focus.
- Optional "Keep the panel clickable" placement.
- Panel and Settings design, four interface languages, Overlap app icon, full-text preview for long candidates.
