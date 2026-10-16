# DESIGN.md — Translate design system

Status: **Stage 5 (translation service).** Additions since the approved stage-2 design: the opt-in
*Keep the panel clickable* placement (§9), the *no service* footer state (§9), and the provider-based service
section of the Translation settings page (§10). Stage history: stage 2 approved direction B, the Overlap icon
and the lead preview.
- Direction B (“Panel”) was selected and refined; direction A has been removed from code (archived in
  `docs/archive/stage1-prototype-src`).
- The app icon **Overlap** was selected (§12).
- The **lead preview** for long translations was approved and implemented (§9.1).

Code: tokens in `prototype/src/styles/tokens.css`, Tailwind mapping in `prototype/src/styles/index.css`,
components in `prototype/src/ui/`, `prototype/src/bars/Panel.tsx`, `prototype/src/settings/`, icons in
`prototype/src/icons/`.

---

## 1. Principles

1. **The panel is a guest.** It sits on someone else's app, under someone else's candidate window. It
   shows key, translation and original, nothing decorative. Detail (full text, source, reasons) appears
   only when it adds something.
2. **The translation is the content; everything else is a label.** One strong text tone per row.
   Keys, originals and status use muted tones. Accent appears on interaction (Alt held, selection), on
   the single primary action in a window, and in the healthy-status dot.
3. **Stable geometry.** Rows have fixed height. Width fits content but only grows during one
   composition. Status always lives in the footer.
4. **Structure is felt, not drawn.** Settings group content in cards. Inside a card, rows are separated
   by one hairline. Nothing gets both a border and a fill unless it is a control.
5. **Same logic in light and dark.** Elevation is a lightness step in OKLCH; dark does not simply invert.
6. **Keyboard parity.** Every pointer action has a key, and every key action has visible feedback.
7. **Quiet by default, explicit when attention is needed.** No tray icon, no chatter. Blocking problems
   surface in the panel footer, plus one notification.

## 2. Typography

Inter Variable (bundled) carries Latin and digits. CJK falls through to the Windows UI face for the
element's `lang`: zh-CN → Microsoft YaHei UI; ja → Yu Gothic UI → Meiryo UI; ko → Malgun Gothic.
Translations carry `lang` = target language. Originals carry `lang="zh-CN"`. Numbers that align use
`tabular-nums`. Chinese copy puts a space between CJK and Latin runs (“正在翻译为 English”).

| Token | Use | Spec |
|---|---|---|
| `text-22` | Page title | 22/28 · 600 · −0.01em |
| `text-14` | Section title, overview status | 14/20 · 600 |
| `text-13` | Body, row labels (500), controls, panel text default | 13/20 |
| `text-12` | Descriptions, originals, footer | 12/16 · 400 |
| `text-11` | Key chips, captions | 11/16 · 500–600 |

Panel translation text: setting 12–16 px (default 13), line-height round(1.4×). Weight token
`--bar-fw` is 500 in light and 450 in dark, because light-on-dark renders heavier.

## 3. Color

OKLCH throughout. Cool porcelain neutrals (hue 250, chroma ≤ .012), jade accent.

| Semantic token | Role | Light | Dark |
|---|---|---|---|
| `app` / `side` | Window background / sidebar (same) | .975 | .19 |
| `surface` / `raised` / `sunken` | Cards / popovers & menus / wells and key chips | 1.0 / 1.0 / .962 | .225 / .255 / .17 |
| `hover` / `press` / `select` | Overlays (fg at 5 / 8.5 / 6.5–7%) | | |
| `line-soft` / `line` / `line-strong` | Card edges & dividers / control edges / tracks, emphasis | 7 / 11 / 19% | 6 / 9.5 / 16% |
| `fg` / `fg-2` / `fg-3` / `fg-4` | Content / secondary / originals, metadata / placeholder, disabled | .24 / .45 / .58 / .71 | .945 / .77 / .61 / .48 |
| `accent` (+ hover, soft, text) | Primary action, Alt-held keys, selection, healthy dot | jade `.56 .11 172` | jade `.68 .11 172` |
| `danger` / `warning` / `success` | Failure / degraded / healthy | | |

Status color goes on the icon. Text stays neutral, except for a rejected key (the user must act).
Contrast: fg ≥ 12:1, fg-2 ≥ 7:1, fg-3 ≥ 4:1 on surfaces. fg-4 is used only for placeholders, disabled
text and the arrow glyph.

## 4. Space, size, radius, elevation

Spacing: 4 px base with 2 px half-steps: 2, 4, 6, 8, 10, 12, 14, 16, 20, 24, 28, 32.

| Metric | Value |
|---|---|
| Control height `--ctl-h` | 32 |
| Settings row min-height `--row-h` | 52 |
| Settings window | 860 × 620, sidebar 216 |
| Panel row | 28 (comfortable) / 24 (compact) at 13 px; scales with text size |
| Panel key chip | 16 / 15 |
| Panel footer | 24 |
| Panel width | content-fit, 216–320 at 13 px (16.6–24.6 × text size), grow-only per composition |
| Radii xs / sm / md / lg / xl | 4 / 6 / 8 / 10 / 12 |

Radius by hierarchy: key chips `xs`, menu items `sm`, controls and rows `md`, popovers `lg`, cards and
the panel `xl`. Shadows are layered: a 1 px ring, a contact shadow and an ambient shadow. Tokens:
`--sh-control`, `--sh-pop` and `--sh-window`. The floating panel and its lead preview are **flat**: `--sh-bar` is
a 1 px border only (14% ink in light, 16% white in dark), no drop shadow — the border and the 97% opaque
background define them on any app.

## 5. Icons (UI)

Lucide, one library. 12 px (stroke 2.25) in the panel, 14 px (stroke 2) in menus and dense UI, 16 px
(stroke 1.75) in settings navigation. Muted at rest; status icons take the status color. Icon-only
buttons need an `aria-label` and a tooltip.

## 6. Interaction states

| State | Treatment |
|---|---|
| Hover | `hover` overlay; text one tone up |
| Pressed | `press` overlay; primary uses `accent-hover` |
| Selected (nav) | Raised surface + hairline + accent icon |
| Keyboard focus | 2 px `focus` outline, 1 px offset, `:focus-visible` only |
| Disabled | Secondary/ghost/danger: 45% opacity. Primary: neutral sunken fill + fg-4 text |
| Error | danger inset ring + halo on focus; message in `danger-text` |
| Panel: Alt held | Key chips fill with accent |
| Panel: inserted | `accent-soft` row + accent text for 150 ms, then the composition clears |
| Panel: unavailable | 300 ms nudge + one-line notice under the panel (1.5 s) |
| Panel: context menu open | Row stays highlighted until the menu closes |

## 7. Motion

`--dur-1` 90 ms (hover/press), `--dur-2` 140 ms (popover, flash, switch), `--dur-3` 200 ms (window).
Out-easing `cubic-bezier(.2,.7,.2,1)`. Things that move: popovers (fade + 3 px), the switch thumb and
the nudge. Under reduced motion there is no pop, and the nudge becomes a dashed outline.

**Desktop app rendering budget** (stage 3, measured):
- Loading placeholders are **static** in the app; the prototype's shimmer is gone. An animated
  placeholder repaints the whole transparent window every frame.
- `backdrop-filter` is not used in the app. An Electron window cannot blur the desktop behind it, so
  the effect only cost compositing.
- The app renders in software, without the GPU process. That is pixel-identical for these surfaces
  and saves about 75 MB.

## 8. Components

Button (primary / secondary / ghost / danger × sm 24 / md 32), IconButton, TextInput (with suffix slot),
Select, Switch (30 × 18), Segmented, Slider, Kbd / Shortcut, Menu, ContextMenu, Tooltip, Message,
Section (card) + Row, SettingsWindow, Panel, LeadPreview, BarMenu, TargetSwitch. Every popover renders
through a `Scope` portal so it inherits the theme. Element resets live in `@layer base` so utilities
always win. (An unlayered `button{color:inherit}` in stage 1 silently overrode text-color utilities.)

## 9. Translation panel specification

| Topic | Decision |
|---|---|
| Structure | Rows: key chip · translation · original (right-aligned, ≤ 28% of the width). 24 px footer: language pair or status, plain text (0.1.0: the ⋯ menu was removed) |
| Number ↔ translation | 16 px chip column, 8 px gap; reads as a key; Alt fills all chips with accent |
| Translation as primary | Only fg-tone text in the row; the original is 12 px fg-3, and fg-2 on hover |
| Footprint | Content-fit width 216–320 px; 28 px rows. Five short words ≈ 216 × 177 px (stage 1: 300 × 205, about 38% less area). Optional compact density, 24 px rows |
| Stability | Fixed row height; width grows within a composition and never shrinks until the next one; skeletons sized from candidate length. Within a composition a row that is still translating keeps the previous keystroke's text at 45% opacity (≤ 600 ms after the last keystroke) instead of flashing to a skeleton — the lead-preview rule (§9.1) applied to rows |
| Long text | Truncates in its row. The full text appears in the **lead preview** (§9.1): automatically for a cut-off #1, on hover for other cut-off rows, and by key on request. The old per-row peek is removed, so long text has exactly one place |
| Failure | “Failed” row; the preview explains the reason and offers Retry; clicking the row retries. If the footer names a list-wide cause, the rows show neutral text |
| Footer, healthy | `● 中 → EN`: plain text showing the language pair. The target language is changed in Settings (0.1.0: the footer dropdown was removed) |
| Footer, degraded | Offline / local-only / unreachable / key rejected / paused, each with a status-colored icon |
| Footer, no service | `📖 Dictionary only — set up a service` (neutral book icon): no key or model yet. Cache and dictionary still translate; other rows show *No local entry* |
| Footer, simulated (test builds only) | `⚗ Simulated translations — not real`: the replay test source with the `[sim]` translator. Never shown in normal use since stage 5 |
| Pointer | Click inserts; right-click shows Insert · Copy · Retry. The panel never takes focus from the app |
| Keyboard | Alt+1…9 insert, Alt+Shift+1…9 copy, Alt+0 hide or show the panel; Alt+` show or hide the full text, Alt+↑/↓ preview another candidate, Alt+PgUp/PgDn scroll it (all only while a list is visible) |
| Readability | `--bar-bg` at 97% opacity by default (setting 70–100%), backdrop blur, a 1 px border (no shadow) |
| Screen edges | The stack flips above the caret near the bottom and slides left near the right edge. The lead preview places itself (§9.1) |
| Finding the bar | WeType draws its bar somewhere inside a larger transparent canvas (628×314 at 96 dpi); where depends on the WeType version, its layout (pinyin above or inline), the display scaling and edge flips, and its messages don't say. The engine renders that window alone into memory (`PrintWindow`, full content), takes the box of drawn pixels and discards the image (~8 ms, cached 50 ms). If the bar isn't drawn yet it uses the last box measured at that size (else a default band) and measures again 60–180 ms later. The panel is anchored to that box, left-aligned with it |
| Opacity | Opaque by default (Appearance › Panel opacity, 90–100 %). The blur behind the panel can't reach other apps, so lower values let their text show through |
| IME window and the mouse | WeChat Input Method's candidate window runs with UIAccess: it sits in a z-band above every normal window, and its whole canvas (628×314 at 96 dpi, transparent parts included) takes the mouse. A panel directly under the bar therefore displays correctly and works by keyboard, but takes no clicks, hover or wheel. **Appearance › Keep the panel clickable** (off by default) places the panel, and the lead preview, clear of that window instead: further from the candidates, fully clickable. With no room clear of it on either side, it falls back to the bar. A UIAccess build (signed, installed under Program Files) would remove the trade-off |

### 9.1 Lead preview

| Topic | Decision |
|---|---|
| Purpose | Read the complete translation of candidate 1 (the usual case) without leaving the input; inspect others on demand |
| Trigger (*Automatic*, default) | #1 is done, cut off in its row, and stable for 200 ms. Once shown, it stays for the rest of the composition |
| *On request* / *Off* | *On request*: only via hover on a cut-off row or the keys. *Off*: no preview at all. Setting: Appearance › Full text of candidate 1 (previews live) |
| Content | Number chip (accent; danger for failures), full translation at text size + 1 with line height ×1.45, then the original, *Insert* (Alt+N) and *Copy*. Failures show the reason and *Retry* |
| Size | Width max(panel width, 360) up to 400. Height fits the text up to 6 lines, then scrolls inside with a bottom fade. Height only grows within a composition |
| Stability | Content swaps in place with no animation. While the new #1 is still translating, the previous text stays at 45% opacity with a hairline progress line for ≤ 600 ms, then two skeleton lines. Rows above never move |
| Other rows | Hovering a cut-off or failed row for 150 ms moves the same card to that row; it returns to #1 300 ms after leaving. Alt+↓/↑ step through candidates |
| Placement | `src/layout/placePreview.ts`, pure DIP geometry, reused by Electron. Order: **outer side** (away from the caret) → **beside** (more room; top-aligned with row 1) → **best fit ≥ 2 lines, scrolls** → **overlay on our own rows** (only on Alt+`) → **none** (row 1 shows ⋯). Never covers the typing band or the IME window; stays inside the monitor's work area with an 8 px margin |
| Dismissal | Commit or cancel of the composition, panel hidden, pause, focus moving to another app. × or Alt+` collapses it for the current composition only. Esc belongs to the IME |
| Focus | The body is passive: no insert on click, no text selection. Every mousedown is swallowed; the wheel scrolls it. Only *Insert* / Alt+N insert |

## 10. Settings model

Pages: **Overview** (status + pause + target language, setup checklist, how to reach the app without a
tray) · **General** (languages, startup, shortcuts incl. copy) · **Translation** (lookup order, local
dictionary, service: provider — OpenAI, Claude, Gemini, Grok, OpenCode Go, DeepSeek, Custom — endpoint,
authentication, key, model with *Load models*, timeout, JSON output, *Test connection*) · **Appearance** (live preview first; theme, text size, density, opacity,
offset, originals) · **Privacy** · **About**.

Keys: typed into the draft, handed to Windows Credential Manager on **Save**, then cleared from the window;
the field then shows a saved-key placeholder. One key per provider. config.json never holds a key.

Edits go to a draft. **Live preview** applies immediately to theme, text size, density, opacity, offset,
original-text mode, the full-text preview mode and interface language. Everything else takes effect on **Save**. A persistent footer
shows the unsaved count, and Cancel/Save are disabled when there is nothing to save. Cancel restores
the saved values, including previewed ones. Settings opens on **Overview**.

## 11. Background presence (no tray icon)

| Need | How |
|---|---|
| Open settings | Run Translate again (single-instance hand-off) · **Ctrl+Alt+O** · notification button |
| Pause / resume | **Ctrl+Alt+P** · Overview switch · settings sidebar |
| Change target language | Overview · General |
| Hide panel | **Alt+0** |
| Read a long translation | Automatic lead preview · **Alt+`** · Alt+↑/↓ |
| Quit | About → Quit |
| Attention | Panel footer status (always) + one notification per blocking incident |
| Start with Windows | General › Start with Windows (on by default): a per-user Run entry for this `Translate.exe`, re-synced at every start |

## 12. App icon: Overlap (selected)

A square (block script) and a circle (round script) overlap; the shared lens is pale jade. Final assets
are in `assets/icons/app/`:
- `translate.ico` with eight exact bitmaps: 16, 20, 24, 32, 40, 48, 64 and 256. The 16 and 20 px frames
  are the hand-hinted 16-grid drawing, verified byte-for-byte.
- `app-*.png`, `app.svg` (48-grid) and `app-small.svg` (16-grid).
- `glyph.svg` and `glyph-{16,20,24,32}-{white,black}.png` for monochrome contexts.

The same plated icon serves the Windows light and dark themes (checked on both). Rebuild with
`node scripts/export_icons.mjs && python scripts/build_ico.py`. The other concepts remain in
`prototype/src/icons/concepts.ts` and `assets/icons/concepts/` for reference.

Rules for all concepts:
- No letters or CJK characters.
- One metaphor.
- Built on the 48 px grid on an ink plate (#2F3742 → #161B21, 1 px 10% white edge).
- Jade gradient #45C9A6 → #1F9E81 matches the UI accent.
- A separately hinted 16 px drawing is used at 16–20 px.
- The single-colour glyph is for tray and monochrome contexts.




## 13. Writing and localization

Sentence case, plain verbs, no apologies. Errors say what happened and what to do. The surface is called
“panel” in every language (面板 / パネル / 패널). Language names are written in their own language. Copy
lives in `src/i18n/locales/{zh-CN,en,ja,ko}.json`. The interface language and the target language are
separate settings.
