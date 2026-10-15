import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Bell, KeyRound, Keyboard, MousePointerClick, Power, RefreshCcw, Rocket, Smile, Paperclip } from 'lucide-react'
import { SCENARIOS, buildList, type CandidateList, type Item } from '../data/scenarios'
import { effectiveSettings, useReview, useSettings } from '../store'
import { Scope, useScope } from '../ui/scope'
import { Button, Kbd, Segmented, cx } from '../ui/primitives'
import { BarA } from '../bars/BarA'
import { BarB } from '../bars/BarB'
import { insertable } from '../bars/common'
import { FakeImeWindow, AppGlyph } from '../settings/pages'
import { SettingsA, SettingsB } from '../settings/SettingsWindow'

type Toast = null | 'firstRun' | 'auth' | 'quit'
const ASYNC_SCENARIOS = ['short', 'long'] as const

/**
 * A simulated Windows desktop: a chat app with a text field, a mock WeChat IME
 * candidate window, and the translation bar. Keyboard + mouse behave as the
 * real product will: the field never loses focus when the bar is used.
 */
export function DesktopDemo() {
  const { t } = useTranslation()
  const { dir, theme } = useScope()
  const scenario = useReview((r) => r.scenario)
  const paused = useReview((r) => r.paused)
  const barHidden = useReview((r) => r.barHidden)
  const settingsOpen = useReview((r) => r.settingsOpen)
  const setp = useReview((r) => r.setp)
  const st = useSettings()
  const s = effectiveSettings(st)
  const barTheme = s.theme === 'system' ? theme : s.theme

  const [appTheme, setAppTheme] = useState<'light' | 'dark'>('light')
  const [edge, setEdge] = useState(false)
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
  const timers = useRef<number[]>([])
  const typing = useRef<number | undefined>(undefined)
  const fieldRef = useRef<HTMLDivElement>(null)
  const caretRef = useRef<HTMLSpanElement>(null)
  const deskRef = useRef<HTMLDivElement>(null)
  const stackRef = useRef<HTMLDivElement>(null)
  const [anchor, setAnchor] = useState<{ x: number; top: number; bottom: number } | null>(null)
  const [left, setLeft] = useState(0)

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
      // First item comes from cache instantly; the rest arrive after a short debounce.
      const gen = full.gen
      setList({ ...full, items: full.items.map((it, i) => (i === 0 ? it : { n: it.n, text: it.text, state: 'loading' as const })) })
      full.items.slice(1).forEach((it, i) => {
        const id = window.setTimeout(
          () => setList((l) => (l && l.gen === gen ? { ...l, items: l.items.map((x) => (x.n === it.n ? it : x)) } : l)),
          160 + 140 + i * 90 + Math.random() * 220,
        )
        timers.current.push(id)
      })
    },
    [scenario, paused, s.target, s.count],
  )

  // Re-run current composition when the scenario/target/pause changes.
  useEffect(() => {
    if (pinyin) compose(pinyin)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenario, paused, s.target, s.count])

  const show = (msg: string) => {
    setNotice(msg)
    window.setTimeout(() => setNotice((n) => (n === msg ? null : n)), 1500)
  }

  const commit = (str: string) => {
    clearTimers()
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
    } else openSettings() // second launch → existing instance shows settings
  }
  const togglePause = () => setp({ paused: !useReview.getState().paused })

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
      if (digit === '0') return setp({ barHidden: !barHidden })
      if (list) insertFrom(list.gen, Number(digit))
      return
    }
    if (e.ctrlKey || e.altKey || e.metaKey) return
    if (/^[a-z]$/i.test(e.key)) {
      e.preventDefault()
      return compose(pinyin + e.key.toLowerCase())
    }
    if (pinyin) {
      e.preventDefault()
      if (e.key === 'Backspace') return compose(pinyin.slice(0, -1))
      if (e.key === 'Escape') return compose('')
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
    const step = () => {
      i++
      compose(py.slice(0, i), scn)
      if (i < py.length) typing.current = window.setTimeout(step, 40)
    }
    step()
  }

  /* ---------------- positioning ---------------- */

  useLayoutEffect(() => {
    const c = caretRef.current?.getBoundingClientRect()
    const d = deskRef.current?.getBoundingClientRect()
    if (!c || !d) return
    setAnchor({ x: c.left - d.left, top: c.top - d.top, bottom: c.bottom - d.top })
  }, [pinyin, text, edge, list?.gen, settingsOpen])

  useLayoutEffect(() => {
    const d = deskRef.current?.getBoundingClientRect()
    const w = stackRef.current?.offsetWidth ?? 0
    if (!anchor || !d) return
    // Keep the IME + bar stack inside the screen's right edge.
    setLeft(Math.max(8, Math.min(anchor.x - 10, d.width - w - 12)))
  }, [anchor, list, dir, s.textSize])

  const Bar = dir === 'a' ? BarA : BarB
  const showBar = !!list && !barHidden && !quit
  const placement = edge ? 'above' : 'below'

  return (
    <div className="flex min-h-0 flex-1">
      {/* ---------- Simulated desktop ---------- */}
      <div
        ref={deskRef}
        className="relative min-w-0 flex-1 overflow-hidden"
        style={{
          background:
            'radial-gradient(1200px 600px at 20% 10%, oklch(0.78 0.06 230), transparent), radial-gradient(900px 600px at 90% 90%, oklch(0.62 0.09 280), transparent), oklch(0.7 0.05 250)',
        }}
      >
        <ChatApp
          appTheme={appTheme}
          edge={edge}
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
            className={cx('absolute z-10 flex', placement === 'below' ? 'flex-col' : 'flex-col-reverse')}
            style={{
              left,
              ...(placement === 'below' ? { top: anchor.bottom + 6 } : { bottom: (deskRef.current?.offsetHeight ?? 0) - anchor.top + 6 }),
              gap: s.offsetY,
            }}
          >
            {list && <FakeImeWindow pinyin={pinyin} items={list.items.map((i) => i.text)} />}
            {showBar && (
              <div style={{ marginLeft: s.offsetX }} className={cx('flex', placement === 'below' ? 'flex-col items-start' : 'flex-col-reverse items-start')}>
                <Scope dir={dir} theme={barTheme}>
                  <Bar
                    list={list}
                    s={s}
                    altHeld={alt}
                    flash={flash}
                    nudge={nudge}
                    placement={placement}
                    edge={edge ? 'right' : 'none'}
                    paused={paused}
                    onInsert={(n) => insertFrom(list.gen, n)}
                    onRetry={retry}
                    onPause={togglePause}
                    onHide={() => setp({ barHidden: true })}
                    onSettings={() => openSettings()}
                    onQuit={doQuit}
                  />
                  {notice && (
                    <div className={cx('anim-fade', placement === 'below' ? 'mt-1.5' : 'mb-1.5')}>
                      <span className="inline-flex h-6 items-center rounded-md bg-raised px-2 text-12 text-fg-2 shadow-pop">{notice}</span>
                    </div>
                  )}
                </Scope>
              </div>
            )}
          </div>
        )}

        {settingsOpen && !quit && (
          <div className="absolute inset-0 z-30 flex items-center justify-center p-6" onMouseDown={(e) => e.target === e.currentTarget && setp({ settingsOpen: false })}>
            <div className="anim-pop origin-center" style={{ transform: 'scale(var(--win-scale, 1))' }}>
              {dir === 'a' ? <SettingsA onClose={() => setp({ settingsOpen: false })} onQuit={doQuit} /> : <SettingsB onClose={() => setp({ settingsOpen: false })} onQuit={doQuit} />}
            </div>
          </div>
        )}

        {toast && <SystemToast kind={toast} shortcut={s.shortcuts.settings} onClose={() => setToast(null)} onOpen={() => (setToast(null), openSettings(toast === 'auth' ? 'translation' : undefined))} />}

        <Taskbar quit={quit} />
      </div>

      {/* ---------- Review controls ---------- */}
      <aside className="scroll-quiet flex w-[300px] shrink-0 flex-col gap-5 overflow-y-auto border-l border-line-soft bg-app px-4 py-4 text-13">
        <Panel title="Scenario" hint="Applies to the composition. Same data in A and B.">
          <div className="grid grid-cols-3 gap-1">
            {SCENARIOS.map((x) => (
              <button
                key={x.id}
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => {
                  setp({ scenario: x.id, paused: x.id === 'paused' ? true : x.id === scenario && paused ? true : false })
                  if (x.id !== 'paused' && paused) setp({ paused: false })
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
        </Panel>

        <Panel title="Try it" hint="Click the message field, then:">
          <KeyHint keys={['a–z']} label="Type pinyin (any letters)" />
          <KeyHint keys={['Alt']} label="Hold to highlight shortcut numbers" />
          <KeyHint keys={['Alt', '1–9']} label="Insert that translation" />
          <KeyHint keys={['Alt', '0']} label="Hide or show the bar" />
          <KeyHint keys={['Space']} label="IME commits the Chinese candidate" />
          <KeyHint keys={['Esc']} label="Cancel composition" />
          <div className="flex items-center gap-2 pt-1 text-12 text-fg-3">
            <MousePointerClick className="size-3.5" /> Clicking the bar keeps the field focused: {focused ? <b className="font-medium text-success-text">focused</b> : <b className="font-medium text-fg-2">not focused</b>}
          </div>
        </Panel>

        <Panel title="Without a tray icon" hint="How you reach a background app in the final build.">
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
        </Panel>

        <Panel title="Environment">
          <Row2 label="App behind the bar">
            <Segmented value={appTheme} onValueChange={setAppTheme} options={[{ value: 'light', label: 'Light' }, { value: 'dark', label: 'Dark' }]} />
          </Row2>
          <Row2 label="Caret position">
            <Segmented value={edge ? 'y' : 'n'} onValueChange={(v) => setEdge(v === 'y')} options={[{ value: 'n', label: 'Middle' }, { value: 'y', label: 'Screen edge' }]} />
          </Row2>
          <div className="text-12 text-fg-3 tnum">
            gen {list?.gen ?? '—'} · bar {barHidden ? 'hidden (Alt+0)' : 'visible'} · {paused ? 'paused' : 'active'}
          </div>
        </Panel>
      </aside>
    </div>
  )
}

/* ------------------------------------------------------------------ */

function Panel({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <div>
        <h3 className="text-13 font-semibold text-fg">{title}</h3>
        {hint && <p className="text-12 text-fg-3">{hint}</p>}
      </div>
      {children}
    </section>
  )
}
function KeyHint({ keys, label }: { keys: string[]; label: string }) {
  return (
    <div className="flex items-center gap-2 text-12 text-fg-2">
      <span className="flex min-w-[72px] gap-0.5">
        {keys.map((k) => (
          <Kbd key={k}>{k}</Kbd>
        ))}
      </span>
      {label}
    </div>
  )
}
function Row2({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2 text-12 text-fg-2">
      {label}
      {children}
    </div>
  )
}

/** Neutral stand-in for any app the user types in (Windows 11-ish chat client). */
function ChatApp(p: {
  appTheme: 'light' | 'dark'
  edge: boolean
  messages: string[]
  text: string
  pinyin: string
  focused: boolean
  fieldRef: React.RefObject<HTMLDivElement | null>
  caretRef: React.RefObject<HTMLSpanElement | null>
  onKeyDown: (e: React.KeyboardEvent) => void
  onFocus: () => void
  onBlur: () => void
}) {
  const dark = p.appTheme === 'dark'
  const c = dark
    ? { win: 'oklch(0.22 0 0)', head: 'oklch(0.25 0 0)', line: 'oklch(1 0 0 / 0.08)', fg: 'oklch(0.93 0 0)', fg2: 'oklch(0.65 0 0)', me: 'oklch(0.45 0.1 150)', them: 'oklch(0.3 0 0)', field: 'oklch(0.26 0 0)' }
    : { win: 'oklch(0.97 0 0)', head: 'oklch(0.995 0 0)', line: 'oklch(0 0 0 / 0.08)', fg: 'oklch(0.2 0 0)', fg2: 'oklch(0.5 0 0)', me: 'oklch(0.86 0.12 145)', them: 'oklch(1 0 0)', field: 'oklch(1 0 0)' }
  return (
    <div
      className="absolute flex flex-col overflow-hidden rounded-[8px] shadow-[0_0_0_1px_oklch(0_0_0/0.15),0_20px_50px_oklch(0_0_0/0.25)]"
      style={{
        background: c.win,
        color: c.fg,
        width: 520,
        height: 360,
        fontFamily: '"Segoe UI Variable Text","Segoe UI","Microsoft YaHei UI",sans-serif',
        ...(p.edge ? { right: 16, bottom: 52 } : { left: 48, top: 28 }),
      }}
      lang="zh-CN"
    >
      <div className="flex h-11 items-center gap-2.5 px-4 text-[14px] font-semibold" style={{ background: c.head, borderBottom: `1px solid ${c.line}` }}>
        <span className="inline-flex size-6 items-center justify-center rounded-full text-[11px] text-white" style={{ background: 'oklch(0.6 0.12 250)' }}>
          林
        </span>
        林晓 · 产品组
      </div>
      <div className="flex flex-1 flex-col justify-end gap-2 overflow-hidden px-4 py-3 text-[14px]">
        {p.messages.slice(-4).map((m, i) => {
          const mine = i % 2 === 1 || i >= 2
          return (
            <div key={i} className={cx('max-w-[78%] rounded-[8px] px-3 py-1.5 leading-[20px]', mine ? 'self-end' : 'self-start')} style={{ background: mine ? c.me : c.them, boxShadow: mine ? 'none' : `0 0 0 1px ${c.line}` }}>
              {m}
            </div>
          )
        })}
      </div>
      <div className="flex items-center gap-2 px-3 pb-3 pt-1" style={{ color: c.fg2 }}>
        <Smile className="size-4" />
        <Paperclip className="size-4" />
        <div
          ref={p.fieldRef}
          role="textbox"
          aria-label="Message"
          tabIndex={0}
          onKeyDown={p.onKeyDown}
          onFocus={p.onFocus}
          onBlur={p.onBlur}
          className="flex h-9 min-w-0 flex-1 cursor-text items-center overflow-hidden whitespace-nowrap rounded-[6px] px-3 text-[14px] outline-none"
          style={{ background: c.field, color: c.fg, boxShadow: `0 0 0 1px ${p.focused ? 'oklch(0.55 0.15 250)' : c.line}` }}
        >
          <span>{p.text}</span>
          {p.pinyin && <span className="underline decoration-dotted underline-offset-4" style={{ color: c.fg }}>{p.pinyin}</span>}
          <span ref={p.caretRef} className={cx('inline-block h-[18px] w-px', p.focused && 'animate-[caret_1s_steps(1)_infinite]')} style={{ background: p.focused ? c.fg : 'transparent' }} />
          {!p.text && !p.pinyin && <span style={{ color: c.fg2 }}>{p.focused ? '' : '点击此处，然后输入拼音…'}</span>}
        </div>
      </div>
    </div>
  )
}

function SystemToast({ kind, shortcut, onClose, onOpen }: { kind: Toast; shortcut: string; onClose: () => void; onOpen: () => void }) {
  const { t } = useTranslation()
  const title = kind === 'auth' ? t('bar.status.authLong') : 'Translate is running in the background'
  const body = kind === 'auth' ? 'Translation is limited to the local dictionary until this is fixed.' : `No window or tray icon. Press ${shortcut} or open Translate from Start to change settings.`
  return (
    <div className="anim-pop absolute bottom-[56px] right-3 z-40 w-[360px] rounded-[8px] p-3.5 text-[13px] shadow-[0_0_0_1px_oklch(0_0_0/0.12),0_12px_32px_oklch(0_0_0/0.25)]" style={{ background: 'oklch(0.97 0 0 / 0.97)', color: 'oklch(0.2 0 0)', fontFamily: '"Segoe UI Variable Text","Segoe UI",sans-serif' }}>
      <div className="mb-2 flex items-center gap-2 text-[12px]" style={{ color: 'oklch(0.45 0 0)' }}>
        <AppGlyph size={16} /> Translate
        <button type="button" onClick={onClose} className="ml-auto px-1 hover:opacity-70" aria-label="Dismiss">
          ✕
        </button>
      </div>
      <div className="font-semibold">{title}</div>
      <div className="mt-0.5 leading-[18px]" style={{ color: 'oklch(0.4 0 0)' }}>
        {body}
      </div>
      <div className="mt-3 flex gap-2">
        <button type="button" onClick={onOpen} className="h-8 flex-1 rounded-[4px] text-[13px]" style={{ background: 'oklch(0.92 0 0)' }}>
          {t('bar.menu.settings').replace('…', '')}
        </button>
        <button type="button" onClick={onClose} className="h-8 flex-1 rounded-[4px] text-[13px]" style={{ background: 'oklch(0.92 0 0)' }}>
          OK
        </button>
      </div>
    </div>
  )
}

function Taskbar({ quit }: { quit: boolean }) {
  return (
    <div className="absolute inset-x-0 bottom-0 flex h-10 items-center justify-center gap-1.5 text-[12px]" style={{ background: 'oklch(0.95 0 0 / 0.85)', backdropFilter: 'blur(20px)', fontFamily: '"Segoe UI",sans-serif', color: 'oklch(0.3 0 0)' }}>
      <span className="inline-flex size-7 items-center justify-center rounded-[4px] text-[15px]" style={{ color: 'oklch(0.55 0.15 250)' }}>
        ⊞
      </span>
      <span className="inline-flex size-7 items-center justify-center rounded-[4px] bg-[oklch(1_0_0/0.7)] text-[11px] font-semibold text-white" style={{ background: 'oklch(0.6 0.12 250)' }}>
        林
      </span>
      <span className="absolute right-3 flex items-center gap-3" style={{ color: 'oklch(0.35 0 0)' }}>
        <span title="System tray — Translate has no icon here">^ 中 ENG</span>
        <span className="tnum">20:14</span>
      </span>
      {quit && <span className="absolute left-3" style={{ color: 'oklch(0.45 0 0)' }}>Translate is not running</span>}
    </div>
  )
}
