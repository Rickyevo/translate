# Privacy

Translate works on what you type, so this page states exactly what it reads, what leaves your PC, and what it keeps.
There is no account, no telemetry, no analytics and no update check.

## What Translate reads

- **Microsoft Pinyin's candidate list**, while you compose, through UI Automation — Windows' accessibility interface,
  the same one Narrator uses to read candidates aloud. Nothing is attached to or changed in any process.
- **WeChat Input Method's candidate list and pinyin**, while you compose. Translate attaches to WeType's
  `wetype_server.exe` process with a small native observer and reads the messages WeType sends to its own candidate
  window through bounded shared memory. The original pipe writes continue unchanged when the observation queue is full.
- **The candidate window's position, and where WeType draws its bar inside it**, to place the panel under it.
  Translate renders WeType's candidate window alone into memory (never the screen or other windows), takes the box
  of drawn pixels, and discards the image; only that box's four numbers are used. Nothing is saved or logged.
- **The caret's position in the app you're typing in**, when the app reports one (the standard Windows caret or the
  accessibility caret object), so the panel doesn't cover the line you're typing on. Only its rectangle is read —
  never text.
- **The foreground app's program name, and whether the focused field is a password field.** Translate does nothing
  in password fields or in apps on the excluded list (Settings › Privacy; by default KeePassXC, Remote Desktop and
  1Password).

Password detection uses the standard Windows password-control flag. Custom-rendered password fields and terminal
password prompts may not expose that flag; use Local only mode or exclude the application for sensitive input.

## What leaves your PC

- With a service configured, uncached **candidate texts and the target language** are sent to **the translation
  service you chose**, with your key. Dictionary results can be displayed immediately and then refined by that
  service, so a dictionary hit can still be sent. Nothing is sent to the authors of Translate.
- No translation requests are sent in **Local only** mode or when no service is set up; available cached results
  and the built-in dictionary (Chinese to English) are used instead.
- What the service does with the text is governed by that provider's terms and privacy policy.

## What is stored on your PC

| What | Where | Notes |
|---|---|---|
| Settings | `%APPDATA%\Translate\config.json` | No key and no typed text |
| API keys | Windows Credential Manager, `Translate:service:<provider>` | Stored for your Windows account, separately per provider; never written to config files or logs, never shown back in Settings |
| Translation cache (memory) | — | Every translation of this session; gone when Translate quits |
| Translation cache (disk) | `%APPDATA%\Translate` | Only dictionary headwords of 1–4 Chinese characters, with short translations. Longer text, digits, Latin letters and non-headwords stay in memory. Dictionary membership is a heuristic, not a guarantee that a word is non-sensitive. Encrypted with Windows DPAPI for your Windows account. Clear it in Settings › Privacy |
| Start with Windows | `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, value `Translate` | The path to `Translate.exe`; removed when you turn the setting off |
| Interface cache | `%LOCALAPPDATA%\Translate\WebView2` | The WebView2 profile for Translate's own pages (no browsing; no typed text) |
| Native observer cache | `%LOCALAPPDATA%\Translate\native` | Content-versioned observer DLLs only; no typed text. An inactive DLL stays loaded until the input method exits, so a cached DLL may remain locked until then |
| Diagnostic log | `%APPDATA%\Translate\logs` | States, counts and timings only — never candidate text or translations. Capped at 2 MB. Open it from Settings › Privacy |

## Removing everything

Turn off Settings › General › Start with Windows and save, quit Translate (Settings › About), delete its folder, `%APPDATA%\Translate` and
`%LOCALAPPDATA%\Translate`, and remove the
`Translate:service:` entries in Windows Credential Manager › Windows Credentials.
