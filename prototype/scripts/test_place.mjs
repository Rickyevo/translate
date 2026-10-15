// Unit checks for the preview placement geometry (src/layout/placePreview.ts).
import { createServer } from 'vite'
const server = await createServer({ server: { middlewareMode: true }, logLevel: 'error' })
const { placePreview, intersects } = await server.ssrLoadModule('/src/layout/placePreview.ts')
let fail = 0
const ok = (name, cond, got) => { console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : '  → ' + JSON.stringify(got)}`); if (!cond) fail++ }
const work = { x: 0, y: 0, w: 1280, h: 680 }
const base = (o) => ({ work, width: 360, needH: 150, minH: 72, ...o })
const inside = (r, W = work) => r.x >= W.x && r.y >= W.y && r.x + r.w <= W.x + W.w && r.y + r.h <= W.y + W.h
const clear = (p, avoid) => [...avoid].every((a) => !intersects(p.rect, a))

// Normal: stack opens down, plenty of room.
{ const band = { x: 100, y: 100, w: 500, h: 36 }, ime = { x: 300, y: 142, w: 470, h: 52 }, panel = { x: 300, y: 200, w: 216, h: 177 }
  const p = placePreview(base({ panel, avoid: [band, ime], stack: 'below' }))
  ok('normal → outer below panel', p.kind === 'outer' && p.rect.y === panel.y + panel.h + 6 && !p.scroll, p)
  ok('normal → clear of band/IME/panel', clear(p, [band, ime, panel]) && inside(p.rect), p) }
// Bottom edge: stack flipped up, outer = above.
{ const band = { x: 60, y: 600, w: 500, h: 36 }, ime = { x: 80, y: 542, w: 470, h: 52 }, panel = { x: 80, y: 359, w: 216, h: 177 }
  const p = placePreview(base({ panel, avoid: [band, ime], stack: 'above' }))
  ok('bottom edge → outer above panel', p.kind === 'outer' && p.rect.y + p.rect.h === panel.y - 6, p)
  ok('bottom edge → clear', clear(p, [band, ime, panel]) && inside(p.rect), p) }
// Bottom-right: right screen edge; outer slides left to stay on screen.
{ const band = { x: 760, y: 600, w: 500, h: 36 }, ime = { x: 800, y: 542, w: 470, h: 52 }, panel = { x: 1050, y: 359, w: 216, h: 177 }
  const p = placePreview(base({ panel, avoid: [band, ime], stack: 'above' }))
  ok('bottom-right → outer above, slid inside right edge', p.kind === 'outer' && p.rect.x + p.rect.w <= 1272, p) }
// Small display: no room above → beside (left, away from right edge).
{ const W = { x: 0, y: 0, w: 760, h: 420 }
  const band = { x: 300, y: 360, w: 440, h: 36 }, ime = { x: 470, y: 302, w: 280, h: 52 }, panel = { x: 520, y: 119, w: 216, h: 177 }
  const p = placePreview({ work: W, panel, avoid: [band, ime], stack: 'above', width: 340, needH: 150, minH: 72 })
  ok('small display → beside left', p.kind === 'beside' && p.side === 'left', p)
  ok('small display → clear + inside', clear(p, [band, ime, panel]) && inside(p.rect, W), p) }
// Very small: neither fits the full text → best-fit scroll.
{ const W = { x: 0, y: 0, w: 600, h: 400 }
  const band = { x: 40, y: 350, w: 540, h: 36 }, ime = { x: 300, y: 292, w: 280, h: 52 }, panel = { x: 360, y: 109, w: 216, h: 177 }
  const p = placePreview({ work: W, panel, avoid: [band, ime], stack: 'above', width: 400, needH: 160, minH: 72 })
  ok('very small → scroll at best fit', p.kind === 'scroll' && p.scroll && p.rect.h >= 72 && p.rect.h < 160, p)
  ok('very small → clear + inside', clear(p, [band, ime, panel]) && inside(p.rect, W), p) }
// Nothing fits: none automatically, overlay on request.
{ const W = { x: 0, y: 0, w: 236, h: 300 }
  const band = { x: 0, y: 250, w: 236, h: 40 }, ime = { x: 0, y: 196, w: 236, h: 50 }, panel = { x: 10, y: 14, w: 216, h: 177 }
  const a = placePreview({ work: W, panel, avoid: [band, ime], stack: 'above', width: 340, needH: 160, minH: 72 })
  const b = placePreview({ work: W, panel, avoid: [band, ime], stack: 'above', width: 340, needH: 160, minH: 72, requested: true })
  ok('no room → none', a.kind === 'none', a)
  ok('no room + requested → overlay on own panel, footer free', b.kind === 'overlay' && b.rect.y === panel.y && b.rect.h === panel.h - 25 && !intersects(b.rect, ime) && !intersects(b.rect, band), b) }
await server.close()
console.log(fail ? `${fail} failed` : 'all placement checks passed')
process.exit(fail ? 1 : 0)
