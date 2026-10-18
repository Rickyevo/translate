# Changelog

## 0.2.4 — 2026-10-18

- Lower backend memory use while typing and while idle. WeChat Input Method now uses a small native observer and
  bounded shared memory instead of loading Frida by default. In a 73-second matched-load test, backend working set
  fell from about 117 MiB to 59 MiB (about 50%); this excludes the host, WebView2 and input-method processes.
- If candidate observation falls behind, old candidates are cleared and cannot be inserted; the next fresh
  composition resumes normally. Queues stay bounded instead of growing with input.
- Reconnect to WeChat Input Method after its process restarts. Stopping Translate or losing its heartbeat disables
  observation and releases the shared-memory connection safely.
- Microsoft Pinyin keeps its full UI Automation implementation. Real candidate reading, translations and Alt+1
  insertion were verified with both input methods. The interface, shortcuts and translation-service behavior are
  unchanged; no noticeable candidate or translation latency regression was observed in the matched-load test.

## 0.2.3 — 2026-10-17

- Shortcuts can be changed in Settings › General: Pause, Open Settings and Hide or show the panel. Click the keys and
  press new ones. Translate refuses keys it can't use (no Alt or Ctrl+Shift, a panel key, a Windows key, another
  shortcut's keys) and keys another app already holds, says why, and registers the new keys on Save. Backspace turns
  one off; Reset restores the default. A saved shortcut another app takes is flagged on General and Overview, and the
  flag clears by itself once the other app lets go.
- Hide or show the panel now uses its configured shortcut (it was always Alt+0).
- Overview: one status card (on or paused, and what translates: the service and model, dictionary only with a link to
  set one up, or local only), the target language, an Input methods card with each input method's state (Ready, Not
  running, Starting, Can't connect, Off) and a switch to turn it off, and the everyday shortcuts. It replaces the
  separate service card, the "Reaching Translate" list and the Input method menu in General.
- About: version and license, links to updates, problem reports and third-party licenses, the dictionary attribution
  and Quit. Removed the Copy diagnostics button (it did nothing), the always-"Running" engine row and the duplicate
  input-method states.
- Simpler pages: no page subtitles; Translation drops the lookup-order diagram and shows JSON output only for custom
  services; Privacy folds the password-field note into "Never translate in" and lists what is stored in three rows.
  The sidebar's Pause button is gone (pause from Overview or the shortcut).
- Input-method and shortcut status is pushed to Settings when it changes instead of being polled every two seconds.
- WeChat Input Method shows "Not running" until it starts, instead of "Not connected".
- Fix: pausing with a shortcut while Settings was open could be undone by Settings echoing an older pause state.

## 0.2.2 — 2026-10-16

- Overview and About now show WeChat Input Method and Microsoft Pinyin separately, each with its own connection
  status, instead of showing only the last active adapter. Status updates while Settings is open.

## 0.2.1 — 2026-10-16

- Fix Microsoft Pinyin silently failing to start when the shipped UI Automation wrappers were generated against a
  different Windows system DLL timestamp. Load compatible bindings from the local system, regenerating them in
  memory when needed; no writes to the app directory are required.
- Release verification now initializes Microsoft Pinyin's UI Automation independently of WeChat Input Method.
- The bundled quick-start guide now includes Microsoft Pinyin and the Settings fallback for occupied shortcuts.

## 0.2.0 — 2026-10-16

- **Microsoft Pinyin support.** Translate now also works with Microsoft Pinyin (Windows 11), the input method built
  into Windows. Settings › General › Input method: *Automatic* (whichever one you type with), *WeChat Input Method*
  or *Microsoft Pinyin*. Microsoft Pinyin's candidates are read through UI Automation, with no attachment to any
  process, and Frida is only loaded once WeChat Input Method is actually running. Overview and About name the input
  method in use; About shows the real version (it said "0.1.0 (prototype)").
- **New host: Tauri 2 + the WebView2 Runtime built into Windows**, replacing Electron. The interface code is
  unchanged and pixel-identical (panel, full-text preview and every Settings page, light and dark). Download about
  61 MB instead of 198 MB; unpacked about 156 MB instead of 474 MB. Memory: about 16 MB before the panel is first
  needed (was 74 MB) and about 20 MB after it is released when you stop typing (was 83 MB); about 146 MB while the
  panel and preview are showing (was 123 MB).
- **The panel no longer covers the line you're typing on** near the bottom of the screen. With no room under
  WeType's bar it goes above the bar — and above the typing line, which is right above the bar there. The caret
  comes from the app (system caret or accessibility caret object); without one, a line's height is kept clear.
- **Settings › Overview**: the three-step checklist is replaced by a single *Connect a translation service* card,
  shown only while no service is set up. (Its first step was always done, and its last was just using the app.)
  `progress.json` is no longer written.
- **Candidates no longer go missing in browsers and Chromium apps.** WeType briefly hides and re-shows its candidate
  window mid-composition there; Translate took that as the end of the composition, so the panel vanished and the rest
  of the composition was ignored. A hide now has to last 150 ms to end it.
- The WeType observer re-checks pipe handles it had rejected, so a window opened a moment ago can't inherit a stale
  verdict; password fields are recognised only on real edit controls (the style bit means other things elsewhere).
- Global shortcuts held by another app at startup (e.g. a Translate that is still exiting) are retried for a minute.
- The test-control DevTools port is accepted only together with `--test-control`.

## 0.1.1 — 2026-10-16

- **Panel placement works on other PCs.** The panel was positioned from fixed offsets measured on one WeType layout
  at 100 % scaling, so with another WeType version or layout (for example pinyin shown inline), other display
  scaling, or WeType's bar drawn elsewhere near a screen edge, it was anchored to the wrong place and could cover
  other text. Translate now finds the bar where WeType actually draws it.
- **The panel is opaque by default.** It was 97 % opaque (adjustable down to 70 %), and other apps' text showed
  through it. The default is now 100 % and the minimum 90 %; a saved 97 % becomes 100 %.
- **Settings fits small screens.** It opened at a fixed 860 × 620 and couldn't be resized, so on a 1366 × 768
  screen at 125 % scaling its bottom, including Save, was off-screen. It now fits the screen it opens on and can be
  resized.

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
- The setup checklist's last step ("Type pinyin in any app") never completed. It now completes the first time the
  panel shows you a translation, updates an open Settings window right away, and is remembered across restarts.
- Settings › Overview no longer points to a Start menu entry (the portable release has none) or to the removed menu.
- `SHA256SUMS.txt` and `README-FIRST.txt` in the release had doubled carriage returns, which broke checksum tools.

## Before 0.1.0

Development builds were numbered up to 0.6.1 internally and were never published. Their history is in
`docs/stage1-report.md` … `docs/stage5-report.md` and `docs/release.md`.
