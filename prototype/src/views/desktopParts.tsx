/* Pieces of the simulated desktop: the stand-in chat app, a Windows toast, the taskbar, side-panel helpers. */
import type { CSSProperties } from 'react'
import { useTranslation } from 'react-i18next'
import { Paperclip, Smile } from 'lucide-react'
import { Kbd, cx } from '../ui/primitives'
import { AppMark } from '../icons/AppMark'

export type Toast = null | 'firstRun' | 'auth' | 'quit'

/* ------------------------------------------------------------------ */

export function Section2({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
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
export function KeyHint({ keys, label }: { keys: string[]; label: string }) {
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
export function Row2({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2 text-12 text-fg-2">
      {label}
      {children}
    </div>
  )
}

/** Neutral stand-in for any app the user types in (Windows 11-ish chat client). */
export function ChatApp(p: {
  appTheme: 'light' | 'dark'
  box: CSSProperties
  compact?: boolean
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
        fontFamily: '"Segoe UI Variable Text","Segoe UI","Microsoft YaHei UI",sans-serif',
        ...p.box,
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
        {p.messages.slice(p.compact ? -1 : -4).map((m, i) => {
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

export function SystemToast({ kind, shortcut, onClose, onOpen }: { kind: Toast; shortcut: string; onClose: () => void; onOpen: () => void }) {
  const { t } = useTranslation()
  const title = kind === 'auth' ? t('bar.status.authLong') : 'Translate is running in the background'
  const body = kind === 'auth' ? 'Translation is limited to the local dictionary until this is fixed.' : `No window or tray icon. Press ${shortcut} or open Translate from Start to change settings.`
  return (
    <div className="anim-pop absolute bottom-[56px] right-3 z-40 w-[360px] rounded-[8px] p-3.5 text-[13px] shadow-[0_0_0_1px_oklch(0_0_0/0.12),0_12px_32px_oklch(0_0_0/0.25)]" style={{ background: 'oklch(0.97 0 0 / 0.97)', color: 'oklch(0.2 0 0)', fontFamily: '"Segoe UI Variable Text","Segoe UI",sans-serif' }}>
      <div className="mb-2 flex items-center gap-2 text-[12px]" style={{ color: 'oklch(0.45 0 0)' }}>
        <AppMark size={16} /> Translate
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

export function Taskbar({ quit }: { quit: boolean }) {
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
