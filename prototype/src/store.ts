import { create } from 'zustand'
import type { UiLangPref } from './i18n'
import type { ScenarioId, Target } from './data/scenarios'

export * from './model'
import { DEFAULT_SETTINGS, type IconId, type Page, type Settings, type Theme, type View } from './model'

interface SettingsStore {
  saved: Settings
  draft: Settings
  set: <K extends keyof Settings>(k: K, v: Settings[K]) => void
  save: () => void
  cancel: () => void
  dirtyKeys: () => (keyof Settings)[]
}

const DEMO_SETTINGS: Settings = { ...DEFAULT_SETTINGS, apiKey: typeof window !== 'undefined' && !('translate' in window) ? 'sk-proj-7Hq2••••••••••••••••c9Fd' : '' }

export const useSettings = create<SettingsStore>((set, get) => ({
  saved: DEMO_SETTINGS,
  draft: DEMO_SETTINGS,
  set: (k, v) => set((s) => ({ draft: { ...s.draft, [k]: v } })),
  save: () => set((s) => ({ saved: s.draft })),
  cancel: () => set((s) => ({ draft: s.saved })),
  dirtyKeys: () => {
    const { saved, draft } = get()
    return (Object.keys(draft) as (keyof Settings)[]).filter((k) => JSON.stringify(draft[k]) !== JSON.stringify(saved[k]))
  },
}))

/* ---------------- Review shell + runtime simulation ---------------- */

interface Review {
  theme: Theme
  icon: IconId
  view: View
  scenario: ScenarioId
  page: Page
  paused: boolean
  barHidden: boolean
  settingsOpen: boolean
  /** App version (from the host; the design lab shows 'prototype'). */
  version: string
  setp: (p: Partial<Omit<Review, 'setp'>>) => void
}

const q = new URLSearchParams(typeof location !== 'undefined' ? location.search : '')
const pick = <T extends string>(k: string, allowed: readonly T[], d: T): T =>
  (allowed as readonly string[]).includes(q.get(k) ?? '') ? (q.get(k) as T) : d

export const useReview = create<Review>((set) => ({
  icon: pick('icon', ['underlay', 'refraction', 'overlap', 'fold'] as const, 'overlap'),
  theme: pick('theme', ['light', 'dark'] as const, 'light'),
  view: pick('view', ['desktop', 'states', 'settings', 'components', 'icons'] as const, 'desktop'),
  scenario: pick('scenario', ['sentence', 'short', 'long', 'loading', 'partial', 'failed', 'offline', 'localOnly', 'auth', 'paused'] as const, 'short'),
  page: pick('page', ['overview', 'general', 'translation', 'appearance', 'privacy', 'about'] as const, 'overview'),
  paused: false,
  barHidden: false,
  settingsOpen: false,
  version: 'prototype',
  setp: (p) => set(p),
}))

/** Initial URL overrides for settings (lang, target) so screenshots are reproducible. */
export function applyUrlSettings() {
  const lang = q.get('lang')
  const target = q.get('target') as Target | null
  const patch: Partial<Settings> = {}
  if (lang && ['zh-CN', 'en', 'ja', 'ko', 'system'].includes(lang)) patch.uiLang = lang as UiLangPref
  if (target) patch.target = target
  if (Object.keys(patch).length) useSettings.setState((s) => ({ saved: { ...s.saved, ...patch }, draft: { ...s.draft, ...patch } }))
}

export function syncUrl() {
  const r = useReview.getState()
  const s = useSettings.getState().saved
  const p = new URLSearchParams({ theme: r.theme, icon: r.icon, view: r.view, scenario: r.scenario, page: r.page, lang: s.uiLang, target: s.target })
  history.replaceState(null, '', '?' + p.toString())
}
