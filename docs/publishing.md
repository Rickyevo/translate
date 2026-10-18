# Publishing on GitHub

Repository: https://github.com/Rickyevo/translate

## Push updates

```
git push -u origin main
```

The vendored Frida runtime is not included; `docs/development.md` explains how to restore it.

## Publish version 0.2.4

Releases › Draft a new release:

- **Tag:** `v0.2.4` on `main`. **Title:** `Translate 0.2.4`.
- **Notes:** the contents of `docs/release-notes/0.2.4.md`.
- **Assets:** `release/Translate-0.2.4-win-x64.zip` and `release/SHA256SUMS.txt`.

Or with the GitHub CLI:

```
gh release create v0.2.4 release/Translate-0.2.4-win-x64.zip release/SHA256SUMS.txt --title "Translate 0.2.4" --notes-file docs/release-notes/0.2.4.md
```

## Checked before publishing

- No API keys, tokens, settings, caches, logs or typed text in the repository, its history or the release zip.
- Commits use the GitHub no-reply address.
- Third-party articles, screenshots and logos used during design research are linked, not included.
- Screenshots come from the app's own windows with sample sentences, never the desktop.
