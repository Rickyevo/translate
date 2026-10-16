# Publishing on GitHub

Everything is prepared locally; nothing has been pushed or uploaded. Steps, in order:

## 1. Create the repository

On GitHub, create an **empty** repository (no README, license or .gitignore — they're here already). A name more
specific than "translate" is easier to find, for example `wetype-translate`.

- **Description:** `Live translations of WeChat Input Method (微信输入法) candidates on Windows — insert the translation instead of the Chinese.`
- **Topics:** `wechat-input-method`, `wetype`, `ime`, `translation`, `chinese`, `pinyin`, `windows`, `tauri`, `webview2`, `llm`
- **Social preview** (Settings › General): `screenshots/readme/hero-en-light.png`.
- Optional: turn off Wiki and Projects; turn on Issues.

## 2. Fill in the repository name

`docs/release-notes/0.2.0.md` links to the README and changelog with the placeholder `Rickywu05/wetype-translate`. Replace it with the
real `owner/name`.

## 3. Push

```
git remote add origin https://github.com/Rickywu05/wetype-translate.git
git push -u origin main
```

The repository is about 42 MB, mostly design-stage screenshots and measurements. The vendored Frida runtime (129 MB)
is not included; `docs/development.md` explains how to restore it.

## 4. Create the release

Releases › Draft a new release:

- **Tag:** `v0.2.0` on `main`. **Title:** `Translate 0.2.0`.
- **Notes:** the contents of `docs/release-notes/0.2.0.md`.
- **Assets:** `release/Translate-0.2.0-win-x64.zip` and `release/SHA256SUMS.txt`.

Or with the GitHub CLI:

```
gh release create v0.2.0 release/Translate-0.2.0-win-x64.zip release/SHA256SUMS.txt --title "Translate 0.2.0" --notes-file docs/release-notes/0.2.0.md
```

## Checked before publishing

- No API keys, tokens, settings, caches, logs or typed text in the repository, its history or the release zip.
- Commits use the GitHub no-reply address.
- Third-party articles, screenshots and logos used during design research are linked, not included.
- Screenshots come from the app's own windows with sample sentences, never the desktop.
