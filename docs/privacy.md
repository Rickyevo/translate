# Privacy

Translate works on what you type, so this page states exactly what it reads, what leaves your PC, and what it keeps.
There is no account, no telemetry, no analytics and no update check.

## What Translate reads

- **WeChat Input Method's candidate list and pinyin**, while you compose. Translate attaches to WeType's
  `wetype_server.exe` process with [Frida](https://frida.re) and observes the messages WeType sends to its own
  candidate window. It does not change WeType or what WeType does with your input.
- **The candidate window's position**, to place the panel under it.
- **The foreground app's program name, and whether the focused field is a password field.** Translate does nothing
  in password fields or in apps on the excluded list (Settings › Privacy; by default KeePassXC, Remote Desktop and
  1Password).

## What leaves your PC

- Only when a translation isn't already in the cache or the local dictionary: **the candidate texts on screen and the
  target language**, sent to **the translation service you chose**, with your key. Nothing is sent to the authors of
  Translate or to anyone else.
- Nothing at all in **Local only** mode or when no service is set up — then only the built-in dictionary is used
  (Chinese → English words).
- What the service does with the text is governed by that provider's terms and privacy policy.

## What is stored on your PC

| What | Where | Notes |
|---|---|---|
| Settings | `%APPDATA%\Translate\config.json` | No key and no typed text |
| API keys | Windows Credential Manager, `Translate:service:<provider>` | Read only by Translate; never written to files or logs, never shown back in Settings |
| Translation cache (memory) | — | Every translation of this session; gone when Translate quits |
| Translation cache (disk) | `%APPDATA%\Translate` | Only words of 1–4 Chinese characters that are general dictionary vocabulary, with their translation. Sentences, names, numbers, Latin letters and anything not in the dictionary never reach disk. Encrypted with Windows DPAPI for your Windows account. Clear it in Settings › Privacy |
| Diagnostic log | `%APPDATA%\Translate\logs` | States, counts and timings only — never candidate text or translations. Capped at 2 MB. Open it from Settings › Privacy |

## Removing everything

Quit Translate (panel ⋯ menu or Settings › About), delete its folder and `%APPDATA%\Translate`, and remove the
`Translate:service:` entries in Windows Credential Manager › Windows Credentials.
