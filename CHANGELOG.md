# Changelog

## 0.1.0 — 2026-10-16

First public release.

- Translations of WeChat Input Method candidates in a panel under the candidate window, while you type pinyin.
- Insert a translation with Alt+1…9 or a click, or copy it with Alt+Shift+1…9, without taking focus from your app.
- Full-text preview for long candidates (automatic for candidate 1, Alt+\` on request).
- Built-in CC-CEDICT dictionary for instant Chinese → English words.
- Translation services: OpenAI, Claude, Gemini, Grok, DeepSeek, OpenCode Go, or any OpenAI-, Claude- or
  Gemini-compatible endpoint; keys in Windows Credential Manager.
- Hybrid cache: common words on disk (encrypted), everything else in memory only.
- Seven target languages; interface in English, 简体中文, 日本語 and 한국어; light and dark themes.
- Start with Windows (on by default; Settings › General).
- Portable: Python runtime and all dependencies bundled; no installer, admin rights or other tools needed.

### Changes since the last development build

- **Start with Windows works.** The switch was shown but did nothing; it now adds or removes a per-user startup entry
  for `Translate.exe`, re-synced at every start so a moved folder is picked up.
- **Simpler panel footer.** The ⋯ menu and the target-language dropdown are gone; the footer shows the language pair
  as plain text. Pause, Hide, Settings and Quit stay available from shortcuts and Settings.
- Settings › Overview no longer points to a Start menu entry (the portable release has none) or to the removed menu.
- `SHA256SUMS.txt` and `README-FIRST.txt` in the release had doubled carriage returns, which broke checksum tools.

## Before 0.1.0

Development builds were numbered up to 0.6.1 internally and were never published. Their history is in
`docs/stage1-report.md` … `docs/stage5-report.md` and `docs/release.md`.
