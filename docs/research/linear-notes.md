# Linear reference study — what transfers to a typing companion

Sources (read in full, saved alongside this note):

- `how-we-redesigned-the-linear-ui.md` — *How we redesigned the Linear UI (part Ⅱ)*, 2024
- `behind-the-latest-design-refresh.md` — *A calmer interface for a product in motion*, 2026 refresh
- `settings-are-not-a-design-failure.md` — *Settings are not a design failure*
- `linear-shots/` — product images published in those articles (light/dark themes, sidebar alignment
  grid, inbox view after the redesign, border refresh, tab bar refresh)

## Limits of this study

- No signed-in Linear workspace was available, so I could not inspect live **settings pages**, menus or
  dialogs in both themes. The settings observations below come from the article text and the published
  inbox/sidebar images, not from the settings screens themselves.
- Images are marketing crops at 2× density; spacing values are estimates, not measured from the product.
- Helpful additions if you can provide them: 3–4 screenshots of Linear's *Preferences*, *Account › Security*
  and the command menu, in light and dark, at 100% zoom.

## Principles observed → how this product uses them

| Linear principle (source) | What it means there | Applied here |
|---|---|---|
| **“Don't compete for attention you haven't earned”** (2026 refresh) — sidebar dimmed so content leads | Orientation chrome recedes; the working surface wins | The bar is chrome for someone else's app. It must lose every contest except legibility of the translation. No accent fill at rest, numbers in a muted tone, status only when abnormal. |
| **“Structure should be felt, not seen”** — fewer, softer separators | Borders only where they clarify relations | Bar items are grouped by spacing, not dividers. A uses one hairline only before a status. Settings groups use a single hairline container (A) or a card (B), never both. |
| **Elevation by lightness steps, built in LCH** (2024 redesign) — 3 inputs generate the theme; dark is “profound and neutral”, light “subtle but nuanced” | Surfaces differ by small perceptual steps; same logic in both themes | All tokens are OKLCH. Light and dark use the same ladder (app → side → surface → raised) with ~2–3 L steps. Dark elevation = lighter surface, not heavier shadow. |
| **Warmer, less saturated neutrals; limit chroma in chrome** (2026) | Neutral greys with a hint of warmth feel calmer; accent is rare | Direction A: warm graphite (hue 75, chroma ≤ .006). Direction B deliberately tests the opposite (cool porcelain, hue 250) so you can compare. |
| **Text and neutral icons darker in light / lighter in dark for contrast** (2024) | Contrast is spent on content | Translation text uses the strongest fg token; numbers, originals and status use fg-3. Body text ≥ 4.5:1, secondary ≥ 3:1. |
| **Inter Display for headings, Inter for text** (2024) | One family, expressive only at heading size | Inter Variable for Latin/digits, with script-specific Windows UI fonts (YaHei UI / Yu Gothic UI / Malgun Gothic) as fallbacks. Headings get –0.01em tracking, not a second family. |
| **Precise alignment of icons/labels on a shared grid** (sidebar alignment image) | Alignment is felt after minutes of use | Icon column fixed at 14–16 px, labels start on the same x in nav, menu and settings rows; Kbd chips share a 18 px height with icons. |
| **Compact, rounded, smaller tab/icon sizing** (2026) | Density via size reduction, not cramming | Bar controls are 24 px inside a 30–32 px bar; icons 12–14 px; one radius family per direction. |
| **Settings as onboarding; preferences users shouldn't have to justify** (settings article) | A settings home that teaches; small preferences make people feel at home | Direction B adds an *Overview* page with status, setup checklist and “how to reach Translate” (important without a tray icon). Both expose taste-level preferences (text size, opacity, original text) without burying them. |
| **Keyboard-first, fast** (product-wide) | Every action reachable without the mouse | Alt+1…9 / Alt+0 on the bar, Ctrl+Alt+P / Ctrl+Alt+O globally, all settings controls keyboard-operable with visible focus. |

## What not to copy

- Linear is a destination app; this is a guest layer over other apps. Linear's sidebars, headers and
  dense multi-pane layouts have no place in the bar.
- Linear's indigo accent and brand gradients — the accent here is chosen per direction (cobalt / jade).
- Mac-style traffic lights — Windows caption buttons are used instead.
