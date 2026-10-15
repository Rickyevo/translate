import { Volume2, Wifi, BatteryMedium, ChevronUp } from 'lucide-react'
import { CONCEPTS, type Concept } from '../icons/concepts'
import { AppMark, Glyph } from '../icons/AppMark'
import { useReview } from '../store'
import { Button, cx } from '../ui/primitives'

const APP_SIZES = [256, 48, 32, 24, 16]
const TRAY_SIZES = [16, 20, 24, 32]
const LIGHT_BG = '#F3F3F3' // Windows 11 light Mica-ish
const DARK_BG = '#202020' // Windows 11 dark

/** Icon concepts at real pixel sizes on light and dark Windows backgrounds. */
export function IconsView() {
  const current = useReview((r) => r.icon)
  const setp = useReview((r) => r.setp)
  return (
    <div className="scroll-quiet min-h-0 flex-1 overflow-auto bg-app">
      <div className="mx-auto flex max-w-[1240px] flex-col gap-8 px-8 py-7">
        <header className="flex items-end justify-between gap-6">
          <div>
            <h2 className="text-22 font-semibold tracking-[-0.01em] text-fg">App icon concepts</h2>
            <p className="mt-1 max-w-[720px] text-13 text-fg-3">
              Every size below is drawn at its real pixel size (no scaling). 16–20 px use a separately hinted drawing. Tray glyphs are single-colour, as Windows
              renders them beside system icons. “Use in app” puts the concept into the title bar, settings sidebar, About page and notifications.
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {CONCEPTS.map((c) => (
              <span key={c.id} className="rounded-lg p-1.5" title={c.name} style={{ background: c.id === current ? 'var(--c-accent-soft)' : undefined }}>
                <AppMark id={c.id} size={32} />
              </span>
            ))}
          </div>
        </header>
        {CONCEPTS.map((c, i) => (
          <ConceptCard key={c.id} c={c} n={i + 1} selected={c.id === current} onUse={() => setp({ icon: c.id })} />
        ))}
      </div>
    </div>
  )
}

function ConceptCard({ c, n, selected, onUse }: { c: Concept; n: number; selected: boolean; onUse: () => void }) {
  return (
    <section data-concept={c.id} className={cx('overflow-hidden rounded-xl bg-surface shadow-[var(--sh-control),0_0_0_1px_var(--c-line-soft)]', selected && 'shadow-[var(--sh-control),0_0_0_1.5px_var(--c-accent)]')}>
      <div className="flex items-start gap-4 px-5 pb-3 pt-4">
        <div className="min-w-0 flex-1">
          <h3 className="text-14 font-semibold text-fg">
            <span className="mr-2 text-fg-4 tnum">{n}</span>
            {c.name}
          </h3>
          <p className="mt-1 max-w-[860px] text-13 text-fg-2">{c.idea}</p>
          <p className="mt-1 max-w-[860px] text-12 text-fg-3">
            <span className="text-fg-2">Why: </span>
            {c.why} <span className="text-fg-2">Watch: </span>
            {c.risk}
          </p>
        </div>
        <Button variant={selected ? 'primary' : 'secondary'} onClick={onUse}>
          {selected ? 'In use' : 'Use in app'}
        </Button>
      </div>
      <div className="grid grid-cols-2">
        {(['light', 'dark'] as const).map((th) => (
          <div key={th} className="flex flex-col gap-5 px-5 py-5" style={{ background: th === 'light' ? LIGHT_BG : DARK_BG, color: th === 'light' ? '#1b1b1b' : '#fff' }}>
            <div className="flex items-end gap-6">
              {APP_SIZES.map((s) => (
                <div key={s} className="flex flex-col items-center gap-1.5">
                  <AppMark id={c.id} size={s} />
                  <span className="text-11 opacity-50 tnum">{s}</span>
                </div>
              ))}
            </div>
            <div className="flex items-end gap-8">
              <div className="flex items-end gap-4">
                {TRAY_SIZES.map((s) => (
                  <div key={s} className="flex flex-col items-center gap-1.5">
                    <Glyph id={c.id} size={s} color={th === 'light' ? '#1b1b1b' : '#ffffff'} />
                    <span className="text-11 opacity-50 tnum">{s}</span>
                  </div>
                ))}
                <span className="pb-5 text-11 opacity-50">tray glyph</span>
              </div>
              <TaskbarStrip id={c.id} theme={th} />
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

/** A slice of the Windows 11 taskbar: app button (24 px) + notification area (16 px glyph). */
function TaskbarStrip({ id, theme }: { id: Concept['id']; theme: 'light' | 'dark' }) {
  const fg = theme === 'light' ? '#1b1b1b' : '#ffffff'
  return (
    <div className="ml-auto flex flex-col items-end gap-1.5">
      <div
        className="flex h-12 items-center gap-1 rounded-md px-2"
        style={{ background: theme === 'light' ? 'rgba(238,238,238,.9)' : 'rgba(28,28,28,.92)', boxShadow: theme === 'light' ? 'inset 0 0 0 1px rgba(0,0,0,.06)' : 'inset 0 0 0 1px rgba(255,255,255,.06)', color: fg }}
      >
        <span className="inline-flex size-10 items-center justify-center rounded-[4px]" style={{ background: theme === 'light' ? 'rgba(255,255,255,.7)' : 'rgba(255,255,255,.07)' }}>
          <AppMark id={id} size={24} />
        </span>
        <span className="mx-2 h-6 w-px opacity-15" style={{ background: fg }} />
        <ChevronUp className="size-4 opacity-80" strokeWidth={1.5} />
        <span className="inline-flex size-7 items-center justify-center">
          <Glyph id={id} size={16} color={fg} />
        </span>
        <Wifi className="size-4" strokeWidth={1.5} />
        <Volume2 className="ml-2 size-4" strokeWidth={1.5} />
        <BatteryMedium className="ml-2 size-4" strokeWidth={1.5} />
        <span className="ml-3 text-right text-[11px] leading-[14px]" style={{ fontFamily: 'Segoe UI, sans-serif' }}>
          20:14
          <br />
          2026/10/14
        </span>
      </div>
      <span className="text-11 opacity-50">taskbar 24 px · notification area 16 px</span>
    </div>
  )
}
