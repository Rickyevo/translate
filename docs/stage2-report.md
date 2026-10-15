# Stage 2: panel refinement and icon exploration

## Run it

```
cd D:\toy\translate\prototype
npm run dev        # http://localhost:5320
```

Views: **Desktop** (simulated typing), **Panel states**, **Settings**, **Components**, **Icons**. The
*Icon concept* selector in the top bar places any concept into the title bar, settings sidebar and
notifications, so you can judge it in context.

## 1. Direction B, refined

Start with `screenshots/stage2/compare/before-after-{light,dark}.png`, which shows every state of the
stage-1 B panel next to the refined one.

| # | Issue in stage-1 B | Impact | Change |
|---|---|---|---|
| 1 | Fixed 300 px width, 32 px rows, 26 px footer | Covered ~300 × 205 px of the app for five short words | Content-fit width (216–320 px at 13 px), 28 px rows, 16 px key chips, 24 px footer: **216 × 177 px**, about 38% less area. Optional *Compact* density (24 px rows) in Appearance |
| 2 | Fitting the content risked rows jumping as results arrived | Would break B's main strength | Width can only grow within one composition and resets when the next one starts. Rows keep fixed height. Verified automatically (216 → 320 → stays 320 → next composition 216) |
| 3 | A hover peek opened on every row, even when everything was already visible | Pop-ups for nothing while sweeping the mouse | The peek opens only when the translation is truncated, or to explain a failure |
| 4 | On long phrases, the original took 42%, then 34%, of the width | The translation (the primary content) was cut | The original is capped at 28% and truncates first |
| 5 | The footer only displayed the language pair | Changing the target meant opening settings | The language pair is now a quick switch (`● 中 → EN ▾`). The change applies immediately and focus stays in the app |
| 6 | No way to copy without inserting | Common need: paste the translation elsewhere | **Alt+Shift+1…9** copies. Right-click on a row gives Insert · Copy · Retry |
| 7 | Copy said “bar” everywhere | Inconsistent with the chosen form | Renamed to “panel” in all four languages (面板 / パネル / 패널) |
| 8 | Unlayered `button { color: inherit }` overrode Tailwind text colors | Footer label and ⋯ were invisible in dark mode, and some button tones were wrong | Element resets moved into `@layer base` |
| 9 | Overview showed status and pause only | Settings home lacked the most-changed setting | Overview now holds status, pause and *Translate into*. Settings opens on Overview |
| 10 | “正在翻译为English” | Cramped CJK–Latin run | Space added between CJK and Latin text |

Unchanged on purpose: B's visual character (porcelain neutrals, jade accent, key chips, originals on
the right, card-based settings, persistent save footer).

## 2. Icon exploration

### Research

Notes: `docs/research/icons/`. Microsoft's guidelines (saved as `ms-icon-guidelines.json`):
- one metaphor, no typography;
- a 48 px grid with 2 px exterior radii;
- at most a subtle 120° gradient;
- sizes 16, 20, 24, 32, 48 and 256 at minimum;
- separate light and dark assets.

The reference icons in `refs-sheet.png` show the pattern this product should break:
- **Google Translate** (G/文) and **LibreTranslate** (L/众) are built from letters and characters.
- **DeepL** uses a speech-bubble outline with network nodes.

The utility icons that work at 16 px (Linear, 1Password, Obsidian) share one thing: a single bold
silhouette of two or three primitives.

### Concepts

`screenshots/stage2/icons-sheet.png` shows all four at 256 / 48 / 32 / 24 / 16 px, a 16 px close-up
at 6× (nearest-neighbour, so you can see the pixel fit), and tray glyphs at 32 / 24 / 20 / 16 on
Windows light and dark. `icons-{light,dark}.png` show each concept in a taskbar and notification-area
mock-up.

| | Concept | Idea | Strength | Watch |
|---|---|---|---|---|
| 1 | **Underlay** | A line (what you type) with the jade layer hanging beneath it | Describes the product's exact position; echoes the panel's pills | Diagrammatic; reads as “nested item” to some |
| 2 | **Refraction** | A line passes through glass and leaves shifted | A memorable single gesture; about transformation, not language clichés | The 16 px plated version is the busiest of the four |
| 3 | **Overlap** | A square (block script) and a circle (round script) overlapping in a jade lens | Strongest at 16 px: two filled shapes; explainable in one sentence | Overlapping geometry is a common logo pattern; the square/circle + jade lens has to own it |
| 4 | **Fold** | A line folds back into a new jade line; also echoes the Enter key | The boldest silhouette; an excellent tray glyph | Can recall a magnet or a return arrow |

Rejected while drawing (inspected at real size):
- a two-dash + bar version of Underlay that read as a robot face;
- a callout version that read as a speech bubble;
- a caret-and-hook concept (“Relay”) that read as the letters “IJ”.

**My recommendation: Overlap**, because it is clearest at 16–24 px where the icon is mostly seen
(taskbar, notifications, title bar), and its meaning (two writing systems sharing meaning) fits
without letters. **Fold** is the bolder alternative if you want more character.

Assets for every concept: `assets/icons/concepts/<id>/`, containing `app.svg`, `app-small.svg`,
`glyph.svg`, `app-{16…256}.png` and `tray-{16,20,24,32}-{white,black}.png`.

## 3. Verification record

**Environment**: Windows 11 Pro 10.0.26200, Node 24.18, headless Microsoft Edge via playwright-core.
All results are **simulated in a browser**. Nothing ran in Electron, against the real WeChat IME, or on
physical multi-monitor or high-DPI hardware.

Automated run (`node scripts/interact.mjs`): **26 / 26 passed**. Results are in
`screenshots/stage2/interaction/results.json`, with moment captures alongside.

| Check | Result |
|---|---|
| Translations in candidate order | ✓ |
| Panel fits short content | ✓ 216 px (stage 1: 300) |
| No peek on fully visible rows; peek on truncated rows | ✓ / ✓ |
| Click inserts, field keeps focus, composition clears | ✓ |
| Alt+3 inserts #3 | ✓ |
| Alt+Shift+2 copies #2 (clipboard = “event”), field unchanged | ✓ |
| Right-click menu: Insert + Copy; Insert works; focus returns to the field | ✓ |
| Width grows for long phrases (≤ 320), never shrinks within the composition, resets next time | ✓ 216 → 320 → 320 → 216 |
| Alt+N on a loading row → notice, nothing inserted | ✓ |
| Footer language switch applies immediately; field keeps focus | ✓ |
| Alt+0, Ctrl+Alt+P, Ctrl+Alt+O | ✓ |
| Density previews live, counts as unsaved, Cancel reverts | ✓ |
| Interface language previews on the same page; Cancel restores | ✓ |
| Saved value survives close and reopen | ✓ |
| Screen edge: panel above the caret and on screen | ✓ |
| No runtime errors | ✓ |

Visual checks of the renders: settings in zh-CN, ja and ko (Overview, Appearance); a Japanese target in
the panel; light and dark themes; 125/150/200% device scale (`scaling/`).

**Not yet tested**:
- **Focus and the right-click menu.** In the real product the panel window is non-activating, so its
  right-click menu will be mouse-only. The prototype instead returns focus to the field after the menu
  closes. Both need confirming in Electron.
- **Integration.** Real IME tracking, Unicode insertion, per-monitor DPI, and screen-reader output.
- **Contrast** is still computed from tokens, not measured with a tool.
- **Icons:** only PNG/SVG for now. The `.ico` and the Windows light/dark theme assets come after you
  choose a concept.

## 4. Decisions needed

1. **Icon**: Underlay, Refraction, Overlap (recommended) or Fold, or the changes you want to one of them.
2. Whether the refined panel's footprint, the quick language switch and copy (Alt+Shift+N /
   right-click) match how you want to use it day to day.
3. Then I proceed to stage 3: the Electron shell, the Python backend, and the protocol.
