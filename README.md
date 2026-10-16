# Translate

**See the translation of every WeChat Input Method candidate while you type — and insert the one you want.**

Translate is a small Windows companion for WeChat Input Method (微信输入法, WeType). As you type pinyin, it shows the
translation of each candidate in a panel under the candidate window. Press Alt+1…9 (or click) to type the translation
instead of the Chinese. Long candidates get a full-text preview.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="screenshots/readme/hero-en-dark.png">
  <img alt="The Translate panel listing five WeChat Input Method candidates with their English translations, next to the full-text preview of the first one" src="screenshots/readme/hero-en-light.png">
</picture>

- **Fast:** common words appear instantly from a built-in dictionary; phrases and sentences come from the
  translation service you choose, usually in about 1.5 s, and are cached.
- **Seven target languages:** English, Japanese, Korean, French, German, Spanish and Russian.
- **Your choice of service:** OpenAI, Claude, Gemini, Grok, DeepSeek, OpenCode Go, or any OpenAI-, Claude- or
  Gemini-compatible endpoint, with your own key.
- **Stays out of the way:** never takes focus from the app you're typing in, no window or tray icon, skips password
  fields, and goes away when you stop typing.
- **Private by design:** keys stay in Windows Credential Manager; nothing is sent anywhere except to the service you
  pick; logs never contain what you type. See [Privacy](docs/privacy.md).
- Interface in English, 简体中文, 日本語 and 한국어; light and dark themes.

> [!NOTE]
> Translate is an independent project. It is not made by, affiliated with or endorsed by Tencent or WeChat.

## Requirements

- Windows 10 or 11, x64
- [WeChat Input Method](https://z.weixin.qq.com/) for Windows. Tested with version **3.0.0.34**; see
  [Known limitations](#known-limitations).
- For phrases, sentences and languages other than English: an API key for a translation service. Without one,
  single words are still translated into English by the built-in dictionary.

## Install

1. Download `Translate-<version>-win-x64.zip` from [Releases](../../releases/latest).
2. Unzip it anywhere, for example `%LOCALAPPDATA%\Programs\Translate`.
3. Run `Translate.exe`. No installer, admin rights, Python or other tools are needed.

Translate isn't code-signed yet, so Windows SmartScreen may warn on first launch: choose **More info**, then
**Run anyway**. You can check the download against `SHA256SUMS.txt` from the same release:

```powershell
Get-FileHash .\Translate-0.1.0-win-x64.zip -Algorithm SHA256
```

Nothing appears when it starts: Translate runs in the background, and from then on starts with Windows (you can turn
that off in Settings › General). Type pinyin with WeChat Input Method in any app and
the panel appears under the candidates.

## Set up a translation service

Run `Translate.exe` again, or press **Ctrl+Alt+O**, to open Settings.

1. **Translation › Service:** pick your provider. The endpoint and a default model are filled in; **Load models**
   lists what your key can use.
2. Paste your **API key** and press **Test connection**.
3. **Save.** The key goes to Windows Credential Manager and is never shown again.
4. **Overview › Translate into:** choose the language.

Use a service whose terms allow this kind of use. Some plan-based subscriptions (OpenCode Go, for example) are
intended for coding tools only.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="screenshots/readme/settings-overview-dark.png">
  <img alt="Settings, Overview page: translating into English, WeChat Input Method connected, setup checklist" src="screenshots/readme/settings-overview-light.png" width="640">
</picture>

## Use

| Keys | Action |
|---|---|
| Alt+1 … Alt+9 | Insert that candidate's translation |
| Alt+Shift+1 … 9 | Copy it instead |
| Alt+\` | Show or hide the full text of a long translation |
| Alt+↑ / Alt+↓ | Preview another candidate |
| Alt+PgUp / Alt+PgDn | Scroll the full text |
| Alt+0 | Hide or show the panel |
| Ctrl+Alt+P | Pause or resume translating |
| Ctrl+Alt+O | Open Settings |

Right-click a row to insert, copy or retry it. The panel's footer shows the language pair (**中 → EN**); the target
language, pausing and quitting (under **About**) are in Settings.

To insert with the mouse, turn on **Settings › Appearance › Keep the panel clickable**: WeType's candidate window
covers the area right under the candidates and takes all clicks there, so this setting moves the panel clear of it.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="screenshots/readme/hero-ja-dark.png">
  <img alt="The panel translating candidates into Japanese" src="screenshots/readme/hero-ja-light.png">
</picture>

## Known limitations

- **WeType versions.** Translate reads WeType's internal messages, which aren't a public interface. It is tested with
  WeType 3.0.0.34; a WeType update can stop it from seeing candidates until Translate is updated. Please open an
  issue with your WeType version if that happens.
- **Security software** may flag Translate, because it attaches to another process (WeType's) with Frida to read the
  candidates.
- **Tested on one PC** so far: Windows 11, one monitor, 100 % scaling. Multiple monitors, other display scaling and
  Windows on ARM are untested.
- **No installer or Start menu entry.** Translate starts with Windows by default (Settings › General › Start with
  Windows) from wherever you unzipped it; if you move the folder, run `Translate.exe` once from the new place.
- **Not code-signed.**
- The built-in dictionary covers Chinese → English only.

## Uninstall

Turn off **Settings › General › Start with Windows** and press Save, then quit Translate (Settings › About › Quit).
Delete its folder and `%APPDATA%\Translate`. Remove saved keys in Windows Credential Manager › Windows Credentials: entries starting with `Translate:service:`.

## How it works

An Electron app shows the panel and Settings; a bundled Python engine follows WeChat Input Method and does the
translating. The engine attaches to `wetype_server.exe` with Frida, decodes the candidate lists WeType sends to its
candidate window, and tracks that window's position. Each new list goes through the cache, then the CC-CEDICT
dictionary, then one batched request to your translation service. Inserting a translation cancels the pinyin
composition and types the text with `SendInput`, without taking focus from your app.

More: [Development guide](docs/development.md) · [Design system](DESIGN.md) · [Host ↔ engine protocol](docs/protocol.md) ·
[Release build](docs/release.md) · [Changelog](CHANGELOG.md)

## Build from source

See [docs/development.md](docs/development.md). In short: Node 22+, Python 3.12, Frida 17.23.3 vendored into
`backend/vendor`, then `npm run build` and `node scripts/package.mjs` in `app/`.

## License and credits

Translate is released under the [MIT License](LICENSE).

- The local dictionary is derived from [CC-CEDICT](https://www.mdbg.net/chinese/dictionary?page=cedict)
  (CC BY-SA 4.0).
- Release downloads bundle Electron, Python, Frida and other components under their own licenses; see
  [THIRD_PARTY_NOTICES.txt](app/build/THIRD_PARTY_NOTICES.txt).
