import { useMemo } from 'react'
import { buildList, type ScenarioId } from '../data/scenarios'
import { effectiveSettings, useSettings, type Settings, type Theme } from '../store'
import { Scope } from '../ui/scope'
import { Panel } from '../bars/Panel'
import { LeadPreview } from '../bars/LeadPreview'
import { FakeImeWindow } from '../settings/pages'
import type { BarProps } from '../bars/common'

interface Spec {
  id: string
  title: string
  note: string
  scenario: ScenarioId
  extra?: Partial<BarProps>
  /** Show the lead preview for this candidate under the panel. */
  lead?: number
  settings?: Partial<Settings>
}

const SPECS: Spec[] = [
  { id: 'short', title: 'Short candidates', note: 'All translated. #1 from cache, rest from service.', scenario: 'short' },
  { id: 'long', title: 'Long translation', note: 'Phrase candidates; long text truncates in place.', scenario: 'long' },
  { id: 'loading', title: 'Loading', note: 'Placeholders sized from candidate length.', scenario: 'loading' },
  { id: 'partial', title: 'Partially complete', note: 'Each item resolves independently. #4 failed.', scenario: 'partial' },
  { id: 'failed', title: 'Service unreachable', note: 'Cached #1 still works; others failed.', scenario: 'failed' },
  { id: 'offline', title: 'Offline', note: 'Local dictionary covers words; #5 has no entry.', scenario: 'offline' },
  { id: 'localOnly', title: 'Local-only mode', note: 'Phrases need the service, so they show no entry.', scenario: 'localOnly' },
  { id: 'auth', title: 'Key rejected', note: 'Needs attention: the status says what to do.', scenario: 'auth' },
  { id: 'paused', title: 'Paused', note: 'Shown once per composition, then stays out of the way.', scenario: 'paused' },
  { id: 'compact', title: 'Compact density', note: 'Optional 24 px rows for people who want the smallest panel.', scenario: 'short', settings: { density: 'compact' } },
  { id: 'lead', title: 'Lead preview (automatic)', note: '#1 is cut off, so its full text appears on the outer side. Rows above never move.', scenario: 'sentence', lead: 1 },
  { id: 'leadHover', title: 'Preview another row', note: 'Alt+↓ (or hovering a cut-off row) moves the same card to #2; it returns to #1 afterwards.', scenario: 'sentence', lead: 2, extra: { hoverRow: 2 } },
  { id: 'leadFail', title: 'Preview a failure', note: 'Explains why, offers Retry.', scenario: 'partial', lead: 4, extra: { hoverRow: 4 } },
  { id: 'leadMore', title: 'No room for full text', note: 'Nothing pops up; row 1 shows ⋯ and Alt+` opens it over the panel.', scenario: 'sentence', extra: { leadMore: true } },
  { id: 'alt', title: 'Alt held (keyboard)', note: 'Numbers light up so the key is found without looking.', scenario: 'short', extra: { altHeld: true } },
  { id: 'flash', title: 'Inserted', note: 'Selected item confirms for 150 ms, then the bar clears.', scenario: 'short', extra: { flash: 2, altHeld: true } },
]

export function StatesBoard() {
  const st = useSettings()
  const s = effectiveSettings(st)
  return (
    <div className="scroll-quiet min-h-0 flex-1 overflow-auto bg-app">
      <div className="px-8 py-6">
        <div className="mb-5 flex items-baseline justify-between">
          <div>
            <h2 className="text-18 font-semibold text-fg">Translation panel — every state at 100% scale</h2>
            <p className="text-13 text-fg-3">Rendered at actual pixel size beneath a mock WeChat IME window. Left: light apps, right: dark apps.</p>
          </div>
        </div>
        <div className="flex flex-col">
          {SPECS.map((sp) => (
            <StateRow key={sp.id} sp={sp} s={sp.settings ? { ...s, ...sp.settings } : s} />
          ))}
        </div>
      </div>
    </div>
  )
}

function StateRow({ sp, s }: { sp: Spec; s: ReturnType<typeof effectiveSettings> }) {
  const list = useMemo(() => buildList(sp.scenario, s.target, s.count), [sp.scenario, s.target, s.count])
  const cell = (theme: Theme) => {
    const backdrop =
      theme === 'light'
        ? 'linear-gradient(180deg, oklch(0.985 0 0), oklch(0.955 0.004 250))'
        : 'linear-gradient(180deg, oklch(0.24 0.005 250), oklch(0.17 0.005 250))'
    return (
      <div
        data-cell={`${sp.id}-${theme}`}
        className="relative mb-4 w-max overflow-visible rounded-lg p-4 shadow-[inset_0_0_0_1px_var(--c-line-soft)]"
        style={{ background: backdrop }}
      >
        <div className="flex flex-col items-start" style={{ gap: s.offsetY }}>
          <FakeImeWindow pinyin={list.pinyin} items={list.items.map((i) => i.text)} compact />
          <Scope theme={theme}>
            <div className="flex flex-col items-start gap-1.5">
              <Panel list={list} s={s} paused={sp.scenario === 'paused'} {...sp.extra} />
              {sp.lead && <LeadPreview item={list.items[sp.lead - 1]} s={s} height={undefined} style={{ width: 360 }} />}
            </div>
          </Scope>
        </div>
      </div>
    )
  }
  return (
    <div className="flex gap-6">
      <div className="w-[180px] shrink-0 pt-4">
        <div className="text-13 font-medium text-fg">{sp.title}</div>
        <div className="text-12 text-fg-3">{sp.note}</div>
      </div>
      <div className="flex min-w-0 flex-1 flex-wrap items-start gap-x-4">
        {cell('light')}
        {cell('dark')}
      </div>
    </div>
  )
}
