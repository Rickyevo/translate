/* Lead-preview placement. Pure geometry in device-independent pixels (DIP) of ONE monitor,
 * so the same function can run in the Electron main process in stage 3.
 *
 * Order (first fit wins):
 *   1. outer   — the panel's far side from the caret (below if the stack opens downward, above if flipped)
 *   2. beside  — left or right of the panel, the side with more room
 *   3. scroll  — wherever has the most height, if ≥ minH; content scrolls
 *   4. overlay — only on explicit request: over the panel's own rows
 *   5. none    — not enough room anywhere; nothing shown automatically
 * Never intersects `avoid` (typing band, IME window) or the panel; always inside the work area.
 */

export interface Rect {
  x: number
  y: number
  w: number
  h: number
}

export type PlacementKind = 'outer' | 'beside' | 'scroll' | 'overlay' | 'none'

export interface PlaceInput {
  work: Rect // monitor work area (excludes taskbar)
  panel: Rect
  avoid: Rect[] // typing band, IME candidate window
  stack: 'below' | 'above' // which way the IME window + panel open from the caret
  width: number // preferred preview width
  needH: number // height the full text needs (already capped at max lines)
  minH: number // smallest useful height (2 lines)
  requested?: boolean // user pressed the preview key (enables overlay fallback)
  margin?: number
  gap?: number
}

export interface Placement {
  kind: PlacementKind
  rect: Rect
  scroll: boolean // content taller than rect
  side?: 'left' | 'right'
}

const right = (r: Rect) => r.x + r.w
const bottom = (r: Rect) => r.y + r.h
export const intersects = (a: Rect, b: Rect) => a.x < right(b) && right(a) > b.x && a.y < bottom(b) && bottom(a) > b.y

/** Free vertical intervals in column [x, x+w] of the work area, after removing blockers. */
function freeIntervals(x: number, w: number, top: number, btm: number, blockers: Rect[], gap: number): [number, number][] {
  const cuts = blockers
    .filter((b) => x < right(b) && x + w > b.x)
    .map((b) => [b.y - gap, bottom(b) + gap] as [number, number])
    .sort((a, b) => a[0] - b[0])
  const out: [number, number][] = []
  let cur = top
  for (const [a, b] of cuts) {
    if (a > cur) out.push([cur, Math.min(a, btm)])
    cur = Math.max(cur, b)
    if (cur >= btm) break
  }
  if (cur < btm) out.push([cur, btm])
  return out.filter(([a, b]) => b - a > 0)
}

interface Option {
  kind: 'outer' | 'beside'
  side?: 'left' | 'right'
  x: number
  avail: number
  /** Position for a given height. */
  y: (h: number) => number
}

export function placePreview(i: PlaceInput): Placement {
  const m = i.margin ?? 8
  const gap = i.gap ?? 6
  const W = { l: i.work.x + m, t: i.work.y + m, r: right(i.work) - m, b: bottom(i.work) - m }
  const w = Math.min(i.width, W.r - W.l)
  const blockers = [...i.avoid, i.panel]
  const opts: Option[] = []

  // 1. Outer side: same left edge as the panel, slid left to stay on screen.
  {
    const x = Math.max(W.l, Math.min(i.panel.x, W.r - w))
    const iv = freeIntervals(x, w, W.t, W.b, blockers, gap)
    if (i.stack === 'below') {
      const start = bottom(i.panel) + gap
      const seg = iv.find(([a, b]) => a <= start + 0.5 && b > start)
      if (seg) opts.push({ kind: 'outer', x, avail: seg[1] - start, y: () => start })
    } else {
      const end = i.panel.y - gap
      const seg = iv.find(([a, b]) => b >= end - 0.5 && a < end)
      if (seg) opts.push({ kind: 'outer', x, avail: end - seg[0], y: (h) => end - h })
    }
  }

  // 2. Beside: right or left of the panel, top-aligned with row 1.
  for (const side of ['right', 'left'] as const) {
    const x = side === 'right' ? right(i.panel) + gap : i.panel.x - gap - w
    if (x < W.l || x + w > W.r) continue
    const iv = freeIntervals(x, w, W.t, W.b, blockers, gap)
    const anchor = i.panel.y // reading starts at row 1
    // The interval containing the anchor, or the nearest one.
    const seg = iv.find(([a, b]) => a <= anchor && anchor <= b) ?? iv.sort((p, q) => Math.abs((p[0] + p[1]) / 2 - anchor) - Math.abs((q[0] + q[1]) / 2 - anchor))[0]
    if (!seg) continue
    const [a, b] = seg
    opts.push({
      kind: 'beside',
      side,
      x,
      avail: b - a,
      y: (h) => Math.max(a, Math.min(i.panel.y, b - h)), // top-align with row 1; slide up only if needed
    })
  }
  // Prefer the beside option with more room.
  const beside = opts.filter((o) => o.kind === 'beside').sort((p, q) => q.avail - p.avail)
  const ordered = [...opts.filter((o) => o.kind === 'outer'), ...beside]

  for (const o of ordered) {
    if (o.avail >= i.needH) return { kind: o.kind, side: o.side, rect: { x: o.x, y: o.y(i.needH), w, h: i.needH }, scroll: false }
  }

  // 3. Best fit with scrolling.
  const best = [...ordered].sort((p, q) => q.avail - p.avail)[0]
  if (best && best.avail >= i.minH) {
    const h = Math.floor(best.avail)
    return { kind: 'scroll', side: best.side, rect: { x: best.x, y: best.y(h), w, h }, scroll: true }
  }

  // 4. Overlay on our own panel — only when asked.
  if (i.requested) {
    const h = i.panel.h - 25 // rows only; the footer stays visible
    return { kind: 'overlay', rect: { x: i.panel.x, y: i.panel.y, w: i.panel.w, h }, scroll: i.needH > h }
  }

  return { kind: 'none', rect: { x: i.panel.x, y: i.panel.y, w: 0, h: 0 }, scroll: false }
}
