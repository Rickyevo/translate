/* App icon concepts — original, abstract, no letters.
 *
 * Each concept has three drawings:
 *  - app:   48×48 grid (Microsoft icon grid), ink plate, used at ≥ 24 px
 *  - small: 16×16 grid, pixel-hinted, plate, used at 16–20 px (title bar, notifications, Start list @100%)
 *  - glyph: 16×16 monochrome (currentColor), no plate — tray/overlay contexts and single-color needs
 *
 * All strings are plain SVG so the same source feeds the React preview and the PNG/ICO export.
 */
import type { IconId } from '../store'

export const INK_A = '#2F3742' // plate gradient start (top-left, 120°)
export const INK_B = '#161B21' // plate gradient end
export const JADE_A = '#45C9A6'
export const JADE_B = '#1F9E81'
export const PAPER = '#F1F4F6'

export interface Concept {
  id: IconId
  name: string
  idea: string
  why: string
  risk: string
}

export const CONCEPTS: Concept[] = [
  {
    id: 'underlay',
    name: 'Underlay',
    idea: 'A line (what you type) with a jade layer hanging beneath it on a short connector — the translation attached under the candidate row.',
    why: 'Describes the product’s exact position and behaviour, and echoes the panel’s own pill shapes. Quiet, utility-like.',
    risk: 'Connector-and-pill reads as “nested item” to some; it is the most diagrammatic and least emblematic of the four.',
  },
  {
    id: 'refraction',
    name: 'Refraction',
    idea: 'A line passes through a pane of glass and leaves shifted: same meaning, new direction.',
    why: 'A memorable, single-gesture silhouette. Speaks to transformation rather than to “language” clichés (globes, bubbles).',
    risk: 'The diagonal step softens at 16 px; the hinted version keeps it on whole pixels.',
  },
  {
    id: 'overlap',
    name: 'Overlap',
    idea: 'A square (block script) and a circle (round script) overlap; the shared area is where meaning carries over.',
    why: 'Strong at every size — two filled primitives survive down to 16 px. Abstract but explainable in one sentence.',
    risk: 'Geometric overlaps are a common logo pattern; needs the specific square/circle pairing and jade lens to own it.',
  },
  {
    id: 'fold',
    name: 'Fold',
    idea: 'A ribbon of text runs forward, folds back and continues as a new line in jade — the same line, turned into another language. The turn also echoes the Enter key: pick, and it’s inserted.',
    why: 'One continuous stroke, the boldest silhouette of the four; stays legible as a tray glyph.',
    risk: 'A thick U-turn can recall a magnet or a “return” arrow; the two-tone split is what makes it read as a line becoming another.',
  },
]

const defs = (u: string) => `
  <defs>
    <linearGradient id="ink-${u}" x1="0" y1="0" x2="1" y2="1" gradientTransform="rotate(-15 .5 .5)">
      <stop offset="0" stop-color="${INK_A}"/><stop offset="1" stop-color="${INK_B}"/>
    </linearGradient>
    <linearGradient id="jade-${u}" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="${JADE_A}"/><stop offset="1" stop-color="${JADE_B}"/>
    </linearGradient>
  </defs>`

/** 48-grid plate: 40×40 at (4,4), radius 10 — Windows-friendly soft square. */
const plate48 = (u: string) =>
  `<rect x="4" y="4" width="40" height="40" rx="10" fill="url(#ink-${u})"/><rect x="4.5" y="4.5" width="39" height="39" rx="9.5" fill="none" stroke="#fff" stroke-opacity=".1"/>`
/** 16-grid plate: full bleed with 0.5 inset so the edge lands on a pixel. */
const plate16 = (u: string) => `<rect x="0.5" y="0.5" width="15" height="15" rx="3.5" fill="url(#ink-${u})" stroke="#fff" stroke-opacity=".12" stroke-width=".5"/>`

const ART: Record<IconId, { app: (u: string) => string; small: (u: string) => string; glyph: string }> = {
  underlay: {
    app: (u) => `
      <path d="M13.5 15V27.5A2.5 2.5 0 0 0 16 30H19" fill="none" stroke="${PAPER}" stroke-opacity=".45" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
      <rect x="10" y="11" width="28" height="7" rx="3.5" fill="${PAPER}"/>
      <rect x="19" y="24.5" width="19" height="11" rx="5.5" fill="url(#jade-${u})"/>`,
    small: (u) => `
      <path d="M4.5 5V10H6.5" fill="none" stroke="${PAPER}" stroke-opacity=".5" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
      <rect x="3" y="3" width="10" height="3" rx="1.5" fill="${PAPER}"/>
      <rect x="6.5" y="8" width="6.5" height="4.5" rx="2.25" fill="url(#jade-${u})"/>`,
    glyph: `
      <path d="M3 4.5V11.5H6" fill="none" stroke="currentColor" stroke-opacity=".55" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"/>
      <rect x="1" y="1.5" width="14" height="4" rx="2" fill="currentColor" fill-opacity=".55"/>
      <rect x="6" y="8.5" width="9" height="6" rx="3" fill="currentColor"/>`,
  },
  refraction: {
    app: (u) => `
      <rect x="18" y="9" width="12" height="30" rx="3.5" fill="#fff" fill-opacity=".12" stroke="#fff" stroke-opacity=".22" stroke-width="1.25"/>
      <path d="M9.5 17.5H18.5" stroke="${PAPER}" stroke-width="4.5" stroke-linecap="round"/>
      <path d="M18.5 17.5L29.5 30.5H38.5" stroke="url(#jade-${u})" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"/>`,
    small: (u) => `
      <rect x="6.5" y="3.5" width="3" height="9" rx="1" fill="#fff" fill-opacity=".14" stroke="#fff" stroke-opacity=".38"/>
      <path d="M3 6.5H6.5" stroke="${PAPER}" stroke-width="1.75" stroke-linecap="round"/>
      <path d="M6.5 6.5L9.5 9.5H13" stroke="url(#jade-${u})" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"/>`,
    glyph: `
      <rect x="6.25" y="1.75" width="3.5" height="12.5" rx="1.25" fill="none" stroke="currentColor" stroke-opacity=".5" stroke-width="1.25"/>
      <path d="M1.5 5.5H6.5L9.5 10.5H14.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>`,
  },
  overlap: {
    app: (u) => `
      <clipPath id="sq-${u}"><rect x="10" y="11" width="19" height="19" rx="4.5"/></clipPath>
      <rect x="10" y="11" width="19" height="19" rx="4.5" fill="${PAPER}"/>
      <circle cx="29" cy="28" r="10" fill="url(#jade-${u})"/>
      <circle cx="29" cy="28" r="10" fill="#C9F2E6" clip-path="url(#sq-${u})"/>`,
    small: (u) => `
      <clipPath id="sq16-${u}"><rect x="3" y="3" width="7" height="7" rx="1.5"/></clipPath>
      <rect x="3" y="3" width="7" height="7" rx="1.5" fill="${PAPER}"/>
      <circle cx="10" cy="10" r="3.75" fill="url(#jade-${u})"/>
      <circle cx="10" cy="10" r="3.75" fill="#C9F2E6" clip-path="url(#sq16-${u})"/>`,
    glyph: `
      <mask id="ov-m"><rect width="16" height="16" fill="#fff"/><circle cx="10" cy="10" r="5.25" fill="#000"/></mask>
      <rect x="1.5" y="1.5" width="9" height="9" rx="2" fill="currentColor" fill-opacity=".55" mask="url(#ov-m)"/>
      <circle cx="10" cy="10" r="4.5" fill="currentColor"/>`,
  },
  fold: {
    app: (u) => `
      <path d="M11 17H29.5" stroke="${PAPER}" stroke-width="8" stroke-linecap="round"/>
      <path d="M29.5 17A7.5 7.5 0 0 1 29.5 32H19" fill="none" stroke="url(#jade-${u})" stroke-width="8" stroke-linecap="round"/>`,
    small: (u) => `
      <path d="M4 5.5H10" stroke="${PAPER}" stroke-width="3" stroke-linecap="round"/>
      <path d="M10 5.5A2.75 2.75 0 0 1 10 11H7" fill="none" stroke="url(#jade-${u})" stroke-width="3" stroke-linecap="round"/>`,
    glyph: `
      <path d="M2.5 5H10.5" stroke="currentColor" stroke-opacity=".55" stroke-width="3.25" stroke-linecap="round"/>
      <path d="M10.5 5A3.5 3.5 0 0 1 10.5 12H6" fill="none" stroke="currentColor" stroke-width="3.25" stroke-linecap="round"/>`,
  },
}

let uid = 0
/** Full-colour icon. Picks the hinted 16-grid drawing for ≤ 20 px. */
export function iconSvg(id: IconId, size: number) {
  const u = `${id}${++uid}`
  if (size <= 20) return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 16 16" fill="none">${defs(u)}${plate16(u)}${ART[id].small(u)}</svg>`
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 48 48" fill="none">${defs(u)}${plate48(u)}${ART[id].app(u)}</svg>`
}

/** Single-colour glyph for tray / monochrome contexts. */
export function glyphSvg(id: IconId, size: number, color = 'currentColor') {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 16 16" fill="none" style="color:${color}">${ART[id].glyph}</svg>`
}
