import { useCallback, useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from 'react'
import { useTranslation } from 'react-i18next'
import { Bell, KeyRound, Keyboard, MousePointerClick, Power, RefreshCcw, Rocket } from 'lucide-react'
import { SCENARIOS, buildList, type CandidateList, type Item } from '../data/scenarios'
import { effectiveSettings, useReview, useSettings } from '../store'
import { Scope, useScope } from '../ui/scope'
import { Button, Segmented, cx } from '../ui/primitives'
import { Panel } from '../bars/Panel'
import { LeadPreview, leadLineHeight } from '../bars/LeadPreview'
import { insertable } from '../bars/common'
import { placePreview, type Placement, type Rect } from '../layout/placePreview'
import { FakeImeWindow } from '../settings/pages'
import { SettingsWindow } from '../settings/SettingsWindow'
import { ChatApp, KeyHint, Row2, Section2, SystemToast, Taskbar, type Toast } from './desktopParts'

const ASYNC_SCENARIOS = ['short', 'long', 'sentence'] as const
export type DeskLayout = 'middle' | 'bottom' | 'corner' | 'small' | 'tiny' | 'cramped'
const LAYOUTS: { id: DeskLayout; label: string }[] = [
  { id: 'middle', label: 'Normal' },
  { id: 'bottom', label: 'Bottom edge' },
  { id: 'corner', label: 'Bottom-right' },
  { id: 'small', label: 'Small display' },
  { id: 'tiny', label: 'Very small' },
  { id: 'cramped', label: 'Cramped' },
]
const TASKBAR = 40
/** Simulated smaller monitors (DIP work areas) for the space-constrained cases. */
const FRAMES: Partial<Record<DeskLayout, Rect>> = {
  small: { x: 24, y: 24, w: 1000, h: 400 },
  tiny: { x: 24, y: 24, w: 720, h: 400 },
  cramped: { x: 24, y: 24, w: 720, h: 330 },
}

const q = new URLSearchParams(location.search)
const initialLayout = (LAYOUTS.find((l) => l.id === q.get('layout'))?.id ?? 'middle') as DeskLayout

const rel = (el: Element | null | undefined, desk: DOMRect): Rect | null => {
  if (!el) return null
  const r = el.getBoundingClientRect()
  return { x: r.left - desk.left, y: r.top - desk.top, w: r.width, h: r.height }
}
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)

/**
 * A simulated Windows desktop: a chat app with a text field, a mock WeChat IME
 * candidate window, the translation panel and its lead preview. Keyboard and mouse
 * behave as the real product will: the field never loses focus.
 */
export function DesktopDemo() {
  const { t } = useTranslation()
  const { theme } = useScope()
  const scenario = useReview((r) => r.scenario)
  const paused = useReview((r) => r.paused)
  const barHidden = useReview((r) => r.barHidden)
  const settingsOpen = useReview((r) => r.settingsOpen)
  const setp = useReview((r) => r.setp)
  const st = useSettings()
  const s = effectiveSettings(st)
  const barTheme = s.theme === 'system' ? theme : s.theme

  const [appTheme, setAppTheme] = useState<'light' | 'dark'>('light')
  const [layout, setLayout] = useState<DeskLayout>(initialLayout)
  const [messages, setMessages] = useState<string[]>(['明天下午三点开会，记得带上周的数据。', 'OK，我准备一下'])
  const [text, setText] = useState('')
  const [pinyin, setPinyin] = useState('')
  const [list, setList] = useState<CandidateList | null>(null)
  const listRef = useRef<CandidateList | null>(null)
  listRef.current = list
  const [focused, setFocused] = useState(false)
  const [alt, setAlt] = useState(false)
  const [flash, setFlash] = useState<number>()
  const [nudge, setNudge] = useState<number>()
  const [notice, setNotice] = useState<string | null>(null)
  const [quit, setQuit] = useState(false)
  const [toast, setToast] = useState<Toast>(null)
  const [composition, setComposition] = useState(0)
  const [ctxOpen, setCtxOpen] = useState<number>()
  const timers = useRef<number[]>([])
  const typing = useRef<number | undefined>(undefined)
  const fieldRef = useRef<HTMLDivElement>(null)
  const caretRef = useRef<HTMLSpanElement>(null)
  const deskRef = useRef<HTMLDivElement>(null)
  const stackRef = useRef<HTMLDivElement>(null)
  const imeRef = useRef<HTMLDivElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const measureRef = useRef<HTMLDivElement>(null)
  const previewScroll = useRef<HTMLDivElement>(null)
  const [desk, setDesk] = useState({ w: 1140, h: 816 })
  const [anchor, setAnchor] = useState<{ x: number; top: number; bottom: number } | null>(null)
  const [dir, setDir] = useState<'below' | 'above'>('below')
  const [left, setLeft] = useState(0)
  const [geom, setGeom] = useState<{ ime: Rect; panel: Rect; band: Rect } | null>(null)

  // Lead preview state (reset per composition).
  const [leadTruncated, setLeadTruncated] = useState(false)
  const [leadSticky, setLeadSticky] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const [requested, setRequested] = useState(false)
  const [kbTarget, setKbTarget] = useState<number>()
  const [hoverTarget, setHoverTarget] = useState<number>()
  const hoverTimer = useRef<number | undefined>(undefined)
  const [needH, setNeedH] = useState(0)
  const [contentOverflow, setContentOverflow] = useState(false)
  const grownH = useRef({ key: -1, h: 0 })
  const lastText = useRef<{ n: number; text: string } | null>(null)
  const [staleOk, setStaleOk] = useState(true)
  const placementRef = useRef<string | undefined>(undefined)

  const work: Rect = FRAMES[layout] ?? { x: 0, y: 0, w: desk.w, h: desk.h - TASKBAR }

  const clearTimers = () => {
    timers.current.forEach((id) => window.clearTimeout(id))
    timers.current = []
  }

  /** New candidate list for this pinyin — obsolete async work is dropped. */
  const compose = useCallback(
    (py: string, scn = scenario) => {
      clearTimers()
      setPinyin(py)
      if (!py) return setList(null)
      const effScn = paused ? 'paused' : scn
      const full = buildList(effScn, s.target, s.count)
      if (!(ASYNC_SCENARIOS as readonly string[]).includes(effScn)) return setList(full)
      // Short words: #1 comes from cache instantly. Phrases: everything goes to the service.
      const gen = full.gen
      const cached = effScn === 'short'
      setList({ ...full, items: full.items.map((it, i) => (i === 0 && cached ? it : { n: it.n, text: it.text, state: 'loading' as const })) })
      full.items.slice(cached ? 1 : 0).forEach((it, i) => {
        const id = window.setTimeout(
          () => setList((l) => (l && l.gen === gen ? { ...l, items: l.items.map((x) => (x.n === it.n ? it : x)) } : l)),
          160 + 140 + i * 90 + Math.random() * 220,
        )
        timers.current.push(id)
      })
    },
    [scenario, paused, s.target, s.count],
  )

  // Re-run the current composition when the scenario/target/pause changes.
  useEffect(() => {
    if (pinyin) compose(pinyin)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenario, paused, s.target, s.count])

  // New composition → preview state resets.
  useEffect(() => {
    setLeadSticky(false)
    setCollapsed(false)
    setRequested(false)
    setKbTarget(undefined)
    setHoverTarget(undefined)
    lastText.current = null
  }, [composition])

  const show = (msg: string) => {
    setNotice(msg)
    window.setTimeout(() => setNotice((n) => (n === msg ? null : n)), 1500)
  }

  const commit = (str: string) => {
    clearTimers()
    setComposition((c) => c + 1)
    setText((x) => x + str)
    setPinyin('')
    setList(null)
  }

  const insertFrom = (gen: number, n: number) => {
    const l = listRef.current
    if (!l || barHidden || paused) return
    if (l.gen !== gen) return show(t('bar.stale'))
    const item: Item | undefined = l.items[n - 1]
    if (!item) return
    if (!insertable(item)) {
      setNudge(n)
      window.setTimeout(() => setNudge(undefined), 320)
      return show(t('bar.unavailable'))
    }
    setFlash(n)
    window.setTimeout(() => {
      setFlash(undefined)
      const sep = /^[a-z]/i.test(item.translation!) && /[a-z.,!?]$/i.test(text) ? ' ' : ''
      commit(sep + item.translation!)
    }, 150)
  }

  const copy = (n: number) => {
    const item = listRef.current?.items[n - 1]
    if (!item || !insertable(item)) {
      setNudge(n)
      window.setTimeout(() => setNudge(undefined), 320)
      return show(t('bar.unavailable'))
    }
    navigator.clipboard?.writeText(item.translation!).catch(() => {})
    show(`${t('bar.copied')} — ${item.translation}`)
  }

  const retry = (n: number) => {
    const gen = list?.gen
    setList((l) => (l ? { ...l, items: l.items.map((x) => (x.n === n ? { n, text: x.text, state: 'loading' } : x)) } : l))
    const done = buildList('short', s.target, s.count).items[n - 1] ?? buildList('long', s.target, s.count).items[n - 1]
    const id = window.setTimeout(() => setList((l) => (l && l.gen === gen ? { ...l, items: l.items.map((x) => (x.n === n ? { ...done, text: x.text, translation: done.translation } : x)) } : l)), 600)
    timers.current.push(id)
  }

  const openSettings = (page?: Parameters<typeof setp>[0]['page']) => setp({ settingsOpen: true, ...(page ? { page } : {}) })
  const doQuit = () => {
    clearTimers()
    setPinyin('')
    setList(null)
    setp({ settingsOpen: false })
    setQuit(true)
    setToast(null)
  }
  const relaunch = () => {
    if (quit) {
      setQuit(false)
      setToast('firstRun')
    } else openSettings() // second launch → the running instance shows settings
  }
  const togglePause = () => setp({ paused: !useReview.getState().paused })

  /* ---------------- lead preview: what to show ---------------- */

  const leadOff = s.leadMode === 'off'
  const panelVisible = !!list && !barHidden && !quit && list.banner !== 'paused'
  const target = hoverTarget ?? kbTarget ?? 1
  const targetItem = list?.items[target - 1]
  const previewWanted = panelVisible && !leadOff && !!targetItem && ((leadSticky && !collapsed) || requested || kbTarget !== undefined || hoverTarget !== undefined)

  // Automatic: #1 done, cut off in its row, stable for 200 ms → sticky for the rest of the composition.
  const item1 = list?.items[0]
  useEffect(() => {
    if (s.leadMode !== 'auto' || leadSticky || collapsed || !leadTruncated || item1?.state !== 'done') return
    const id = window.setTimeout(() => setLeadSticky(true), 200)
    return () => window.clearTimeout(id)
  }, [s.leadMode, leadSticky, collapsed, leadTruncated, item1?.state, list?.gen])

  // Keep the last shown text so a new #1 that is still translating doesn't blank the card (≤ 600 ms).
  if (targetItem?.state === 'done' && targetItem.translation) lastText.current = { n: target, text: targetItem.translation }
  const stale = targetItem?.state === 'loading' && staleOk && lastText.current?.n === target ? lastText.current.text : undefined
  useEffect(() => {
    if (targetItem?.state !== 'loading') return setStaleOk(true)
    const id = window.setTimeout(() => setStaleOk(false), 600)
    return () => window.clearTimeout(id)
  }, [targetItem?.state, list?.gen])

  const onHoverRow = (n: number | undefined, eligible?: boolean) => {
    window.clearTimeout(hoverTimer.current)
    if (n !== undefined && eligible) hoverTimer.current = window.setTimeout(() => setHoverTarget(n), hoverTarget === undefined ? 150 : 60)
    else hoverTimer.current = window.setTimeout(() => setHoverTarget(undefined), 300)
  }
  const keepHover = () => window.clearTimeout(hoverTimer.current)

  const hidePreview = () => {
    setCollapsed(true)
    setRequested(false)
    setKbTarget(undefined)
    setHoverTarget(undefined)
  }
  const togglePreview = () => {
    // Hide only what is actually on screen; with no room, the key opens the overlay instead.
    if (previewWanted && placementRef.current !== 'none') return hidePreview()
    setCollapsed(false)
    setRequested(true)
  }
  const step = (d: 1 | -1) => {
    if (!list) return
    const max = list.items.length
    const cur = kbTarget ?? hoverTarget ?? 1
    setRequested(true)
    setCollapsed(false)
    setKbTarget(((cur - 1 + d + max) % max) + 1)
  }
  const scrollPreview = (d: 1 | -1) => previewScroll.current?.scrollBy({ top: d * 3 * leadLineHeight(s.textSize) })

  /* ---------------- keyboard ---------------- */

  // Global shortcuts: work whether or not the text field is focused.
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === 'Alt') {
        e.preventDefault()
        setAlt(true)
      }
      if (quit) return
      if (e.ctrlKey && e.altKey && e.code === 'KeyP') (e.preventDefault(), togglePause())
      if (e.ctrlKey && e.altKey && e.code === 'KeyO') (e.preventDefault(), openSettings())
    }
    const up = (e: KeyboardEvent) => e.key === 'Alt' && setAlt(false)
    const blur = () => setAlt(false)
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    window.addEventListener('blur', blur)
    return () => {
      window.removeEventListener('keydown', down)
      window.removeEventListener('keyup', up)
      window.removeEventListener('blur', blur)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [quit])

  const onFieldKey = (e: React.KeyboardEvent) => {
    const digit = /^Digit(\d)$/.exec(e.code)?.[1]
    if (e.altKey && !e.ctrlKey && digit) {
      e.preventDefault()
      if (quit) return
      if (e.shiftKey && digit !== '0') return list ? copy(Number(digit)) : undefined
      if (digit === '0') return setp({ barHidden: !barHidden })
      if (list) insertFrom(list.gen, Number(digit))
      return
    }
    // Preview keys — only while a candidate list is visible.
    if (e.altKey && !e.ctrlKey && panelVisible && !leadOff) {
      if (e.code === 'Backquote') return (e.preventDefault(), togglePreview())
      if (e.key === 'ArrowDown') return (e.preventDefault(), step(1))
      if (e.key === 'ArrowUp') return (e.preventDefault(), step(-1))
      if (e.key === 'PageDown') return (e.preventDefault(), scrollPreview(1))
      if (e.key === 'PageUp') return (e.preventDefault(), scrollPreview(-1))
    }
    if (e.ctrlKey || e.altKey || e.metaKey) return
    if (/^[a-z]$/i.test(e.key)) {
      e.preventDefault()
      return compose(pinyin + e.key.toLowerCase())
    }
    if (pinyin) {
      e.preventDefault()
      if (e.key === 'Backspace') return compose(pinyin.slice(0, -1))
      if (e.key === 'Escape') return (setComposition((c) => c + 1), compose(''))
      if (e.key === ' ' && list) return commit(list.items[0].text)
      if (/^[1-9]$/.test(e.key) && list?.items[Number(e.key) - 1]) return commit(list.items[Number(e.key) - 1].text)
      if (e.key === 'Enter') return commit(pinyin)
      return
    }
    if (e.key === 'Backspace') return (e.preventDefault(), setText((x) => x.slice(0, -1)))
    if (e.key === 'Enter') {
      e.preventDefault()
      if (text.trim()) setMessages((m) => [...m, text])
      return setText('')
    }
    if (e.key.length === 1) return (e.preventDefault(), setText((x) => x + e.key))
  }

  const typeIt = (scn = scenario) => {
    fieldRef.current?.focus()
    const py = SCENARIOS.find((x) => x.id === scn)!.pinyin
    let i = 0
    window.clearTimeout(typing.current)
    const stepType = () => {
      i++
      compose(py.slice(0, i), scn)
      if (i < py.length) typing.current = window.setTimeout(stepType, 30)
    }
    stepType()
  }

  /* ---------------- geometry ---------------- */

  useLayoutEffect(() => {
    const el = deskRef.current
    if (!el) return
    const ro = new ResizeObserver(() => setDesk({ w: el.clientWidth, h: el.clientHeight }))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // Caret anchor, stack direction (flip up when it doesn't fit below), stack x clamped to the work area.
  useLayoutEffect(() => {
    const d = deskRef.current?.getBoundingClientRect()
    const c = caretRef.current?.getBoundingClientRect()
    if (!c || !d) return
    const a = { x: c.left - d.left, top: c.top - d.top, bottom: c.bottom - d.top }
    if (!same(a, anchor)) setAnchor(a)
    const stackH = stackRef.current?.offsetHeight ?? 260
    const stackW = stackRef.current?.offsetWidth ?? 0
    const nextDir = a.bottom + 6 + stackH > work.y + work.h - 8 ? 'above' : 'below'
    if (nextDir !== dir) setDir(nextDir)
    const nextLeft = Math.max(work.x + 8, Math.min(a.x - 10, work.x + work.w - stackW - 8))
    if (nextLeft !== left) setLeft(nextLeft)
  })

  // Measured rects for placement: IME window, panel, typing band (input bounds are known here).
  useLayoutEffect(() => {
    const d = deskRef.current?.getBoundingClientRect()
    if (!d) return
    const ime = rel(imeRef.current, d)
    const panel = rel(panelRef.current?.querySelector('[role=listbox]'), d)
    const field = rel(fieldRef.current, d)
    const next = ime && panel && field ? { ime, panel, band: { x: field.x - 4, y: field.y - 4, w: field.w + 8, h: field.h + 8 } } : null
    if (!same(next, geom)) setGeom(next)
    // Natural preview height at the chosen width (already capped at LEAD_MAX_LINES).
    const m = measureRef.current
    if (m) {
      if (m.offsetHeight !== needH) setNeedH(m.offsetHeight)
      const sc = m.querySelector<HTMLElement>('.scroll-quiet')
      const over = !!sc && sc.scrollHeight > sc.clientHeight + 1
      if (over !== contentOverflow) setContentOverflow(over)
    }
  })

  const previewW = Math.round(Math.min(400, Math.max(360, geom?.panel.w ?? 0)))
  let placement: Placement | null = null
  if (previewWanted && geom && needH > 0) {
    // Height only grows within a composition.
    if (grownH.current.key !== composition) grownH.current = { key: composition, h: 0 }
    grownH.current.h = Math.max(grownH.current.h, needH)
    placement = placePreview({
      work,
      panel: geom.panel,
      avoid: [geom.band, geom.ime],
      stack: dir,
      width: previewW,
      needH: grownH.current.h,
      minH: 30 + 2 * leadLineHeight(s.textSize) + 16,
      requested: requested || kbTarget !== undefined,
    })
  }
  placementRef.current = placement?.kind
  // #1 cut off but nowhere to show it → mark row 1 with ⋯ (Alt+` opens it over the panel).
  const leadMore = panelVisible && leadTruncated && !leadOff && placement?.kind === 'none'

  const showBar = !!list && !barHidden && !quit
  const chatBox: CSSProperties =
    layout === 'middle'
      ? { left: 48, top: 28, width: 520, height: 360 }
      : layout === 'bottom'
        ? { left: 48, bottom: TASKBAR + 12, width: 520, height: 360 }
        : layout === 'corner'
          ? { right: 16, bottom: TASKBAR + 12, width: 520, height: 360 }
          : { left: work.x + work.w - 440 - 12, top: work.y + work.h - 170 - 12, width: 440, height: 170 }

  return (
    <div className="flex min-h-0 flex-1">
      {/* ---------- Simulated desktop ---------- */}
      <div
        ref={deskRef}
        data-desk
        className="relative min-w-0 flex-1 overflow-hidden"
        style={{
          background:
            'radial-gradient(1200px 600px at 20% 10%, oklch(0.78 0.06 230), transparent), radial-gradient(900px 600px at 90% 90%, oklch(0.62 0.09 280), transparent), oklch(0.7 0.05 250)',
        }}
      >
        {FRAMES[layout] && (
          <div
            className="pointer-events-none absolute rounded-[6px] border border-dashed"
            style={{ left: work.x, top: work.y, width: work.w, height: work.h, borderColor: 'oklch(1 0 0 / 0.75)', background: 'oklch(0.3 0.03 250 / 0.16)' }}
          >
            <span className="absolute left-2 top-1.5 text-[12px]" style={{ color: 'oklch(1 0 0 / 0.9)', fontFamily: 'Segoe UI, sans-serif' }}>
              Simulated {({ small: 'small', tiny: 'very small', cramped: 'cramped' } as Record<string, string>)[layout]} display — work area {work.w} × {work.h}
            </span>
          </div>
        )}

        <ChatApp
          appTheme={appTheme}
          box={chatBox}
          compact={!!FRAMES[layout]}
          messages={messages}
          text={text}
          pinyin={pinyin}
          focused={focused}
          fieldRef={fieldRef}
          caretRef={caretRef}
          onKeyDown={onFieldKey}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
        />

        {pinyin && anchor && !quit && (
          <div
            ref={stackRef}
            className={cx('absolute z-10 flex items-start', dir === 'below' ? 'flex-col' : 'flex-col-reverse')}
            style={{ left, ...(dir === 'below' ? { top: anchor.bottom + 6 } : { bottom: desk.h - anchor.top + 6 }), gap: s.offsetY }}
          >
            {list && (
              <div ref={imeRef}>
                <FakeImeWindow pinyin={pinyin} items={list.items.map((i) => i.text)} />
              </div>
            )}
            {showBar && (
              <div ref={panelRef} style={{ marginLeft: s.offsetX }} className="relative">
                <Scope theme={barTheme}>
                  <Panel
                    list={list}
                    compositionKey={composition}
                    ctxOpen={ctxOpen}
                    onCtx={(n) => {
                      setCtxOpen(n)
                      if (n === undefined) window.setTimeout(() => fieldRef.current?.focus(), 0) // the panel never keeps focus
                    }}
                    onCopy={copy}
                    onTarget={(tg) => {
                      useSettings.setState((x) => ({ saved: { ...x.saved, target: tg }, draft: { ...x.draft, target: tg } }))
                      fieldRef.current?.focus()
                    }}
                    hoverRow={hoverTarget}
                    onHoverRow={onHoverRow}
                    onLeadTruncated={(v) => v !== leadTruncated && setLeadTruncated(v)}
                    leadMore={leadMore}
                    s={s}
                    altHeld={alt}
                    flash={flash}
                    nudge={nudge}
                    paused={paused}
                    onInsert={(n) => insertFrom(list.gen, n)}
                    onRetry={retry}
                    onPause={togglePause}
                    onHide={() => setp({ barHidden: true })}
                    onSettings={() => openSettings()}
                    onQuit={doQuit}
                  />
                  {notice && (
                    <div className="anim-fade pointer-events-none absolute inset-x-1 bottom-1 z-10 flex justify-center">
                      <span className="inline-flex h-[22px] max-w-full items-center truncate rounded-md bg-raised px-2 text-12 text-fg-2 shadow-pop">{notice}</span>
                    </div>
                  )}
                </Scope>
              </div>
            )}
          </div>
        )}

        {/* Lead preview: measured off-screen at its width, then placed by placePreview(). */}
        {previewWanted && targetItem && (
          <Scope theme={barTheme}>
            <div ref={measureRef} aria-hidden className="pointer-events-none invisible absolute left-[-10000px] top-0" style={{ width: previewW }}>
              <LeadPreview item={targetItem} s={s} stale={stale} />
            </div>
            {placement && placement.kind !== 'none' && (
              <div
                data-preview={placement.kind}
                className="anim-fade absolute z-20"
                style={{ left: placement.rect.x, top: placement.rect.y, width: placement.rect.w }}
                onMouseEnter={keepHover}
                onMouseLeave={() => hoverTarget !== undefined && onHoverRow(undefined)}
              >
                <LeadPreview
                  ref={previewScroll}
                  item={targetItem}
                  s={s}
                  stale={stale}
                  height={placement.rect.h}
                  overlay={placement.kind === 'overlay'}
                  scrollable={placement.scroll || contentOverflow}
                  onInsert={(n) => list && insertFrom(list.gen, n)}
                  onCopy={copy}
                  onRetry={retry}
                  onCollapse={hidePreview}
                />
              </div>
            )}
          </Scope>
        )}

        {settingsOpen && !quit && (
          <div className="absolute inset-0 z-30 flex items-center justify-center p-6" onMouseDown={(e) => e.target === e.currentTarget && setp({ settingsOpen: false })}>
            <div className="anim-pop origin-center">
              <SettingsWindow onClose={() => setp({ settingsOpen: false })} onQuit={doQuit} />
            </div>
          </div>
        )}

        {toast && <SystemToast kind={toast} shortcut={s.shortcuts.settings} onClose={() => setToast(null)} onOpen={() => (setToast(null), openSettings(toast === 'auth' ? 'translation' : undefined))} />}

        <Taskbar quit={quit} />
      </div>

      {/* ---------- Review controls ---------- */}
      <aside className="scroll-quiet flex w-[300px] shrink-0 flex-col gap-5 overflow-y-auto border-l border-line-soft bg-app px-4 py-4 text-13">
        <Section2 title="Scenario" hint="Applies to the composition.">
          <div className="grid grid-cols-3 gap-1">
            {SCENARIOS.map((x) => (
              <button
                key={x.id}
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => {
                  setp({ scenario: x.id, paused: x.id === 'paused' })
                  typeIt(x.id)
                }}
                className={cx(
                  'focus-ring h-7 truncate rounded-sm px-1.5 text-12 transition-colors',
                  scenario === x.id ? 'bg-accent-soft font-medium text-accent-text' : 'text-fg-2 shadow-[inset_0_0_0_1px_var(--c-line-soft)] hover:bg-hover',
                )}
              >
                {x.label}
              </button>
            ))}
          </div>
          <Button className="mt-1 w-full" onMouseDown={(e) => e.preventDefault()} onClick={() => typeIt()}>
            <Keyboard className="size-3.5" /> Type “{SCENARIOS.find((x) => x.id === scenario)!.pinyin.slice(0, 14)}…” for me
          </Button>
        </Section2>

        <Section2 title="Screen and caret" hint="Where you are typing. The preview places itself.">
          <div className="grid grid-cols-2 gap-1">
            {LAYOUTS.map((l) => (
              <button
                key={l.id}
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => {
                  setLayout(l.id)
                  setComposition((c) => c + 1)
                  window.setTimeout(() => typeIt(), 50)
                }}
                className={cx(
                  'focus-ring h-7 rounded-sm px-1.5 text-12 transition-colors',
                  layout === l.id ? 'bg-accent-soft font-medium text-accent-text' : 'text-fg-2 shadow-[inset_0_0_0_1px_var(--c-line-soft)] hover:bg-hover',
                )}
              >
                {l.label}
              </button>
            ))}
          </div>
          <div className="text-12 text-fg-3 tnum" data-readout>
            Stack opens {dir} · preview{' '}
            {placement ? placement.kind + (placement.side ? ` (${placement.side})` : '') + (placement.scroll ? ', scrolls' : '') : previewWanted ? 'measuring' : 'hidden'}
          </div>
        </Section2>

        <Section2 title="Try it" hint="Click the message field, then:">
          <KeyHint keys={['a–z']} label="Type pinyin (any letters)" />
          <KeyHint keys={['Alt', '1–9']} label="Insert that translation" />
          <KeyHint keys={['Alt', 'Shift', '1–9']} label="Copy instead of insert" />
          <KeyHint keys={['Alt', '`']} label="Show or hide full text" />
          <KeyHint keys={['Alt', '↑↓']} label="Preview another candidate" />
          <KeyHint keys={['Alt', 'PgUp/Dn']} label="Scroll the full text" />
          <KeyHint keys={['Alt', '0']} label="Hide or show the panel" />
          <KeyHint keys={['Right-click']} label="Insert · Copy · Retry" />
          <KeyHint keys={['Esc']} label="Cancel composition" />
          <div className="flex items-center gap-2 pt-1 text-12 text-fg-3">
            <MousePointerClick className="size-3.5" /> Message field:{' '}
            {focused ? <b className="font-medium text-success-text">focused</b> : <b className="font-medium text-fg-2">not focused</b>}
          </div>
        </Section2>

        <Section2 title="Without a tray icon" hint="How you reach a background app in the final build.">
          <Button className="w-full justify-start" onMouseDown={(e) => e.preventDefault()} onClick={relaunch}>
            <Rocket className="size-3.5" /> {quit ? 'Launch Translate.exe' : 'Launch Translate.exe again'}
          </Button>
          <KeyHint keys={s.shortcuts.settings.split('+')} label="Open settings" />
          <KeyHint keys={s.shortcuts.pause.split('+')} label={paused ? 'Resume translation' : 'Pause translation'} />
          <div className="grid grid-cols-2 gap-1.5 pt-1">
            <Button size="sm" onMouseDown={(e) => e.preventDefault()} onClick={() => setToast('firstRun')}>
              <Bell className="size-3" /> First-run notice
            </Button>
            <Button size="sm" onMouseDown={(e) => e.preventDefault()} onClick={() => setToast('auth')}>
              <KeyRound className="size-3" /> Needs attention
            </Button>
          </div>
          <div className="flex items-center gap-2 text-12 text-fg-3">
            {quit ? <Power className="size-3.5" /> : <RefreshCcw className="size-3.5" />}
            {quit ? 'Quit — no background process.' : paused ? 'Running, translation paused.' : 'Running quietly. No window, no tray icon.'}
          </div>
        </Section2>

        <Section2 title="Environment">
          <Row2 label="App behind the panel">
            <Segmented value={appTheme} onValueChange={setAppTheme} options={[{ value: 'light', label: 'Light' }, { value: 'dark', label: 'Dark' }]} />
          </Row2>
          <div className="text-12 text-fg-3 tnum">
            gen {list?.gen ?? '—'} · panel {barHidden ? 'hidden (Alt+0)' : 'visible'} · {paused ? 'paused' : 'active'}
          </div>
        </Section2>
      </aside>
    </div>
  )
}
