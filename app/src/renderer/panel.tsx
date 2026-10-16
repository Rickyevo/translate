/* Panel renderer: the translation panel and its lead preview.
 * The preview lives in a child window opened from this document (window.open), so it shares this
 * renderer process and this React tree — no second renderer for the most frequent extra surface. */
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { createRoot } from 'react-dom/client'
import { create } from 'zustand'
import i18n, { resolveLang } from '../../../prototype/src/i18n'
import { Panel } from '../../../prototype/src/bars/Panel'
import { LeadPreview, leadLineHeight } from '../../../prototype/src/bars/LeadPreview'
import { Scope, POPPER } from '../../../prototype/src/ui/scope'
import type { PanelKey, PanelState, PreviewPlacementMsg, TranslateApi } from '../shared/types'
import './app.css'

const api = (window as unknown as { translate: TranslateApi }).translate
const TEST = new URLSearchParams(location.search).get('test') === '1'
POPPER.avoidCollisions = false // the window grows to fit menus instead
const M = 16

const useApp = create<{ s: PanelState | null; place: PreviewPlacementMsg | null; key: { k: PanelKey; t: number } | null }>(() => ({ s: null, place: null, key: null }))
api.onState((s) => useApp.setState({ s }))
api.onPreviewPlacement((place) => useApp.setState({ place }))
api.onKey((k) => useApp.setState({ key: { k, t: performance.now() } }))

/** Mouse passes through the transparent margins; anything marked as hit-able captures it. */
const HIT = '[data-hit], [data-radix-popper-content-wrapper]'
function trackMouse(doc: Document, which: 'panel' | 'preview') {
  let inside = false
  doc.addEventListener('mousemove', (e) => {
    const now = !!(e.target as Element | null)?.closest?.(HIT)
    if (now !== inside) api.mouseInside(which, (inside = now))
  })
  doc.addEventListener('mouseleave', () => inside && api.mouseInside(which, (inside = false)))
}
trackMouse(document, 'panel')

function PanelApp() {
  const s = useApp((x) => x.s)
  const place = useApp((x) => x.place)
  const key = useApp((x) => x.key)
  const boxRef = useRef<HTMLDivElement>(null)
  const measureRef = useRef<HTMLDivElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Lead preview state, reset per composition (same rules as the prototype, DESIGN §9.1).
  const [leadTruncated, setLeadTruncated] = useState(false)
  const [sticky, setSticky] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const [requested, setRequested] = useState(false)
  const [kb, setKb] = useState<number>()
  const [hover, setHover] = useState<number>()
  const hoverTimer = useRef<number | undefined>(undefined)
  const [ctxOpen, setCtxOpen] = useState<number>()
  const composition = s?.composition ?? 0
  useEffect(() => {
    setSticky(false), setCollapsed(false), setRequested(false), setKb(undefined), setHover(undefined)
  }, [composition])

  useEffect(() => {
    if (s) i18n.changeLanguage(resolveLang(s.settings.uiLang))
  }, [s?.settings.uiLang])

  const list = s?.list ?? null
  const set = s?.settings
  const visible = !!list && !!s && !s.hidden
  const leadOff = set?.leadMode === 'off'
  const target = hover ?? kb ?? 1
  const item = list?.items[target - 1]
  const wanted = visible && !leadOff && !!item && list?.banner !== 'paused' && ((sticky && !collapsed) || requested || kb !== undefined || hover !== undefined)

  const item1 = list?.items[0]
  useEffect(() => {
    if (set?.leadMode !== 'auto' || sticky || collapsed || !leadTruncated || item1?.state !== 'done') return
    const id = window.setTimeout(() => setSticky(true), 200)
    return () => window.clearTimeout(id)
  }, [set?.leadMode, sticky, collapsed, leadTruncated, item1?.state, list?.gen])

  // Keys arrive from main's global shortcuts.
  useEffect(() => {
    if (!key || !list) return
    const k = key.k
    if (k.action === 'togglePreview') {
      if (wanted && place?.kind !== 'none') (setCollapsed(true), setRequested(false), setKb(undefined), setHover(undefined))
      else (setCollapsed(false), setRequested(true))
    } else if (k.action === 'step') {
      const max = list.items.length
      const cur = kb ?? hover ?? 1
      setRequested(true), setCollapsed(false), setKb(((cur - 1 + k.d + max) % max) + 1)
    } else if (k.action === 'scroll') {
      scrollRef.current?.scrollBy({ top: k.d * 3 * leadLineHeight(set!.textSize) })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  // Report content size (and room for open menus) so main can size and place the window.
  // Only changes are sent: an unconditional report would feed back through main's layout reply.
  const lastSize = useRef('')
  const lastRows = useRef('')
  useLayoutEffect(() => {
    const report = () => {
      const box = boxRef.current?.firstElementChild as HTMLElement | null
      if (!box) return
      const r = box.getBoundingClientRect()
      let right = r.right,
        bottom = r.bottom
      document.querySelectorAll('[data-radix-popper-content-wrapper]').forEach((p) => {
        const pr = p.getBoundingClientRect()
        right = Math.max(right, pr.right)
        bottom = Math.max(bottom, pr.bottom)
      })
      const size = [Math.ceil(r.width), Math.ceil(r.height), Math.ceil(right - M), Math.ceil(bottom - M)]
      const sizeKey = size.join(',')
      if (sizeKey !== lastSize.current) {
        lastSize.current = sizeKey
        api.panelSize(size[0], size[1], size[2], size[3])
      }
      if (!TEST) return // row geometry is only needed by the test harness
      const rows = [...document.querySelectorAll<HTMLElement>('[data-row]')].map((el) => {
        const b = el.getBoundingClientRect()
        return { n: Number(el.dataset.row), x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height) }
      })
      const rowsKey = JSON.stringify(rows)
      if (rowsKey !== lastRows.current) {
        lastRows.current = rowsKey
        api.panelRows(rows)
      }
    }
    reportRef.current = report
    report()
  })
  // Observers are created once (not per render: re-observing fires an extra callback each time). The
  // ResizeObserver catches size changes after fonts/layout settle; the MutationObserver only cares about
  // menus (Radix poppers) opening or closing, not about every text swap in the rows.
  // A popper is inserted before it is positioned (floating-ui moves it a frame later via its style, and its
  // content animates in), so measuring only at insertion saw a menu at the origin and the window never grew to fit
  // it: a menu (the row context menu) opened outside its window, invisible and unclickable. The wrapper itself is therefore observed
  // (position via style, size via ResizeObserver) for as long as it is open.
  const reportRef = useRef<() => void>(() => {})
  useLayoutEffect(() => {
    const run = () => reportRef.current()
    const ro = new ResizeObserver(run)
    if (boxRef.current) ro.observe(boxRef.current)
    const isPopper = (n: Node): n is Element => n instanceof Element && n.matches('[data-radix-popper-content-wrapper]')
    const poppers = (n: Node) => (n instanceof Element ? [...(isPopper(n) ? [n] : []), ...n.querySelectorAll('[data-radix-popper-content-wrapper]')] : [])
    const styleMo = new MutationObserver(run)
    const mo = new MutationObserver((ms) => {
      let changed = false
      for (const m of ms) {
        for (const n of m.addedNodes)
          for (const p of poppers(n)) {
            styleMo.observe(p, { attributes: true, attributeFilter: ['style'] })
            ro.observe(p)
            changed = true
          }
        for (const n of m.removedNodes) if (poppers(n).length) changed = true
      }
      if (changed) run()
    })
    mo.observe(document.body, { childList: true, subtree: true })
    return () => (ro.disconnect(), mo.disconnect(), styleMo.disconnect())
  }, [!!s?.list])

  // Preview need: measured here at its width; main decides placement.
  const previewW = 380
  const lastNeed = useRef('')
  useLayoutEffect(() => {
    const h = measureRef.current?.offsetHeight ?? 0
    const need = { wanted: wanted && h > 0, requested: requested || kb !== undefined, w: previewW, h }
    const key = JSON.stringify(need)
    if (key !== lastNeed.current) {
      lastNeed.current = key
      api.previewNeed(need)
    }
  })

  const child = usePreviewWindow(wanted)

  if (!s || !list || !set) return <div ref={boxRef} />
  const theme = s.theme
  const leadMore = visible && leadTruncated && !leadOff && place?.kind === 'none'

  return (
    <Scope theme={theme} className="contents">
      <div ref={boxRef} style={{ position: 'absolute', left: M, top: M }}>
        <div data-hit className="relative inline-block">
          <Panel
            list={list}
            s={set}
            paused={s.paused}
            compositionKey={composition}
            hoverRow={hover}
            onHoverRow={(n, eligible) => {
              window.clearTimeout(hoverTimer.current)
              if (n !== undefined && eligible) hoverTimer.current = window.setTimeout(() => setHover(n), hover === undefined ? 150 : 60)
              else hoverTimer.current = window.setTimeout(() => setHover(undefined), 300)
            }}
            onLeadTruncated={(v) => v !== leadTruncated && setLeadTruncated(v)}
            leadMore={leadMore}
            ctxOpen={ctxOpen}
            onCtx={setCtxOpen}
            onInsert={(n) => api.insert(list.gen, n)}
            onCopy={(n) => api.copy(list.gen, n)}
            onRetry={(n) => api.retry(list.gen, n)}
          />
          {s.notice && (
            <div className="anim-fade pointer-events-none absolute inset-x-1 bottom-1 z-10 flex justify-center">
              <span className="inline-flex h-[22px] max-w-full items-center truncate rounded-md bg-raised px-2 text-12 text-fg-2 shadow-pop">{i18n.t('bar.' + s.notice.key, { text: s.notice.text })}</span>
            </div>
          )}
        </div>
      </div>
      {wanted && item && (
        <div ref={measureRef} aria-hidden className="pointer-events-none invisible absolute left-[-10000px] top-0" style={{ width: previewW }}>
          <LeadPreview item={item} s={set} />
        </div>
      )}
      {child &&
        wanted &&
        item &&
        place &&
        place.kind !== 'none' &&
        createPortal(
          <Scope theme={theme} className="contents">
            <div data-hit style={{ position: 'absolute', left: M, top: M, width: place.w }}>
              <LeadPreview
                ref={scrollRef}
                item={item}
                s={set}
                height={place.h}
                overlay={place.kind === 'overlay'}
                scrollable={place.scroll}
                onInsert={(n) => api.insert(list.gen, n)}
                onCopy={(n) => api.copy(list.gen, n)}
                onRetry={(n) => api.retry(list.gen, n)}
                onCollapse={() => (setCollapsed(true), setRequested(false), setKb(undefined), setHover(undefined))}
              />
            </div>
          </Scope>,
          child.document.body,
        )}
    </Scope>
  )
}

/** Opens the preview child window once (same renderer process) and copies this document's styles into it. */
const query = new URLSearchParams(location.search)
const SEPARATE = query.get('preview') === 'separate'

function usePreviewWindow(wanted: boolean) {
  const [child, setChild] = useState<Window | null>(null)
  useEffect(() => {
    if (!wanted || child || SEPARATE) return
    const w = window.open('about:blank', 'translate-preview', 'width=400,height=200')
    if (!w) return
    w.document.title = 'Translate preview'
    w.document.documentElement.lang = document.documentElement.lang
    document.head.querySelectorAll('style, link[rel=stylesheet]').forEach((n) => w.document.head.appendChild(n.cloneNode(true)))
    w.document.body.style.cssText = 'margin:0;background:transparent;overflow:hidden'
    trackMouse(w.document, 'preview')
    setChild(w)
  }, [wanted, child])
  return useMemo(() => child, [child])
}

/** Measurement probe: a static lead preview, rendered by its own renderer process (--preview-separate). */
function ProbePreview() {
  const s = useApp((x) => x.s)
  const set = s?.settings
  const item = { n: 1, text: '我们明天下午三点在会议室讨论这个问题', state: 'done' as const, translation: "We'll discuss this in the meeting room at 3 p.m. tomorrow — please have last week's figures ready beforehand." }
  if (!set) return null
  return (
    <Scope theme={s!.theme} className="contents">
      <div style={{ position: 'absolute', left: M, top: M, width: 380 }}>
        <LeadPreview item={item} s={set} height={104} />
      </div>
    </Scope>
  )
}

createRoot(document.getElementById('root')!).render(query.get('probe') ? <ProbePreview /> : <PanelApp />)
