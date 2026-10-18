# Lead preview and final icon (stage 2 addendum)

Approved design: a full-text **lead preview** for long translations, *Automatic* by default, and the
**Overlap** app icon. This records what was built and how it was checked.

## Try it

```
cd prototype
npm run dev        # http://localhost:5320
```

In **Desktop**, press **Sentence** (a long first candidate), then use **Screen and caret** to switch
between *Normal*, *Bottom edge*, *Bottom-right*, *Small display*, *Very small* and *Cramped*. The line
under the buttons reports the placement chosen (`outer`, `beside (left)`, `scroll`, `overlay`, `none`).
Keys:
- **Alt+`**: show or hide the full text
- **Alt+↑/↓**: preview another candidate
- **Alt+PgUp/PgDn**: scroll the full text
- **Alt+1…9**: insert a translation

## What was built

| Part | Where |
|---|---|
| Placement geometry (pure, DIP, reusable by Electron) | `prototype/src/layout/placePreview.ts` |
| Preview card | `prototype/src/bars/LeadPreview.tsx` |
| Trigger, sticky-per-composition, hover/keyboard target, stale text, grow-only height | `prototype/src/views/DesktopDemo.tsx` |
| Panel reports hover and “#1 is cut off”; ⋯ marker when there is no room; old per-row peek removed | `prototype/src/bars/Panel.tsx` |
| Setting *Full text of candidate 1*: Automatic / On request / Off (previews live) | Settings › Appearance |
| New fixed shortcuts listed | Settings › General › Shortcuts |
| Strings in zh-CN, en, ja, ko | `prototype/src/i18n/locales/` |
| Final icon | `assets/icons/app/` (`translate.ico` + PNG/SVG + glyphs) |

## Screenshots

`screenshots/stage2/lead-preview/placement-sheet.png` shows the six placements at a glance.

| Case | File | Result |
|---|---|---|
| Normal | `1-normal.png`, `1-normal-dark.png` | Below the panel (outer side) |
| Bottom edge | `2-bottom-edge.png` | Stack flips up; preview above the panel |
| Bottom-right | `3-bottom-right.png` | Above, slid inside the right edge |
| Small display (1000 × 400) | `4-small-display-beside.png` | Outer side too short → beside, left, top-aligned with row 1 |
| Very small (720 × 400) | `5-very-small-scroll.png`, `6-very-small-scrolled.png` | Neither fits → best fit, height-limited, scrolls (Alt+PgDn shown) |
| Cramped (720 × 330) | `7-cramped-none.png`, `8-cramped-overlay-on-request.png` | Under 2 lines anywhere → nothing automatic, row 1 shows ⋯; Alt+` opens it over the panel's own rows, footer stays visible |
| Hover / step | `9-hover-row-2.png`, `10-step-alt-down.png` | The same card follows the candidate |

The **Panel states** view (`screenshots/stage2/states-{light,dark}.png`) adds four rows: the lead
preview, previewing another row, a failure, and “no room”.

## Verification

Environment: Windows 11 Pro 10.0.26200, headless Microsoft Edge via playwright-core. **Simulated in a
browser only.**

- **Placement geometry**, `node scripts/test_place.mjs`: **11/11 passed**. Covers normal, bottom edge,
  bottom-right, small display (beside), very small (scroll), no room (none), and requested overlay. Each
  case is also checked for no overlap with the typing band, IME window or panel, and for staying inside
  the work area.
- **Interaction**, `node scripts/interact.mjs`: **37/37 passed**. The 11 new checks:
  - No preview when #1 fits.
  - Automatic preview on the outer side, and rows don't move when it appears.
  - The preview sits on the far side of the panel from the caret.
  - Clicking the body inserts nothing and focus stays in the field.
  - The mouse wheel keeps focus.
  - Alt+↓ moves to #2; Alt+` hides and shows.
  - × collapses and keeps focus.
  - *Insert* inserts the previewed candidate and the preview closes with the composition.
  - The *Full text of candidate 1* setting previews live, and Cancel reverts it.
- **Icon**, `python scripts/build_ico.py`: the `.ico` contains 16, 20, 24, 32, 40, 48, 64 and 256 px,
  and the 16 px frame is byte-identical to the hand-hinted bitmap.

**Must still be validated in Electron (stage 3, first)**:
- Whether clicks, wheel scrolling and dragging the scroll thumb take focus.
- Hover in a window that has never been activated.
- Whether Alt+`, Alt+↑/↓ and Alt+PgUp/PgDn reach us during WeChat IME composition.
- Stacking order against the IME window.
- Resizing on every keystroke without lag.
- Placement across monitors with different DPI.
- The caret-side fallback when no caret position is available.

**Known limit**: if the panel itself can't fit above or below the caret (extremely small work areas),
it isn't handled yet. That is a stage-3 positioning task, separate from the preview.
