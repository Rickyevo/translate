import { create } from 'zustand'
import type { UiLangPref } from './i18n'
import type { ScenarioId, Target } from './data/scenarios'

export type Dir = 'a' | 'b'
export type Theme = 'light' | 'dark'
export type View = 'desktop' | 'states' | 'settings' | 'components'
export type OrigMode = 'hover' | 'always' | 'never'
export type ThemePref = 'system' | 'light' | 'dark'
export type Page = 'overview' | 'general' | 'translation' | 'appearance' | 'privacy' | 'about'

/* ---------------- Settings (saved vs. draft) ---------------- */

export interface Settings {
  uiLang: UiLangPref
  target: Target
  count: number
  autostart: boolean
  localDict: boolean
  endpoint: string
  apiKey: string
  model: string
  timeout: number
  jsonMode: boolean
  theme: ThemePref
  textSize: number
  opacity: number
  offsetX: number
  offsetY: number
  showOriginal: OrigMode | 'default'
  localOnly: boolean
  denylist: string[]
  shortcuts: { toggleBar: string; pause: string; settings: string }
}

export const DEFAULT_SETTINGS: Settings = {
  uiLang: 'system',
  target: 'en',
  count: 5,
  autostart: true,
  localDict: true,
  endpoint: 'https://api.openai.com/v1',
  apiKey: 'sk-proj-7Hq2••••••••••••••••c9Fd',
  model: 'gpt-4o-mini',
  timeout: 8,
  jsonMode: true,
  theme: 'system',
  textSize: 13,
  opacity: 0.97,
  offsetX: 0,
  offsetY: 4,
  showOriginal: 'default',
  localOnly: false,
  denylist: ['KeePassXC.exe', 'mstsc.exe', '1Password.exe'],
  shortcuts: { toggleBar: 'Alt+0', pause: 'Ctrl+Alt+P', settings: 'Ctrl+Alt+O' },
}

/** Settings that preview live on the bar before saving. */
export const LIVE_KEYS: (keyof Settings)[] = ['theme', 'textSize', 'opacity', 'offsetX', 'offsetY', 'showOriginal', 'uiLang']

interface SettingsStore {
  saved: Settings
  draft: Settings
  set: <K extends keyof Settings>(k: K, v: Settings[K]) => void
  save: () => void
  cancel: () => void
  dirtyKeys: () => (keyof Settings)[]
}

export const useSettings = create<SettingsStore>((set, get) => ({
  saved: DEFAULT_SETTINGS,
  draft: DEFAULT_SETTINGS,
  set: (k, v) => set((s) => ({ draft: { ...s.draft, [k]: v } })),
  save: () => set((s) => ({ saved: s.draft })),
  cancel: () => set((s) => ({ draft: s.saved })),
  dirtyKeys: () => {
    const { saved, draft } = get()
    return (Object.keys(draft) as (keyof Settings)[]).filter((k) => JSON.stringify(draft[k]) !== JSON.stringify(saved[k]))
  },
}))

/** What the bar currently renders with: live keys from draft, the rest from saved. */
export function effectiveSettings(s: { saved: Settings; draft: Settings }): Settings {
  const out = { ...s.saved }
  for (const k of LIVE_KEYS) (out as Record<string, unknown>)[k] = s.draft[k]
  return out
}

/* ---------------- Review shell + runtime simulation ---------------- */

interface Review {
  dir: Dir
  theme: Theme
  view: View
  scenario: ScenarioId
  page: Page
  paused: boolean
  barHidden: boolean
  settingsOpen: boolean
  setp: (p: Partial<Omit<Review, 'setp'>>) => void
}

const q = new URLSearchParams(location.search)
const pick = <T extends string>(k: string, allowed: readonly T[], d: T): T =>
  (allowed as readonly string[]).includes(q.get(k) ?? '') ? (q.get(k) as T) : d

export const useReview = create<Review>((set) => ({
  dir: pick('dir', ['a', 'b'] as const, 'a'),
  theme: pick('theme', ['light', 'dark'] as const, 'light'),
  view: pick('view', ['desktop', 'states', 'settings', 'components'] as const, 'desktop'),
  scenario: pick('scenario', ['short', 'long', 'loading', 'partial', 'failed', 'offline', 'localOnly', 'auth', 'paused'] as const, 'short'),
  page: pick('page', ['overview', 'general', 'translation', 'appearance', 'privacy', 'about'] as const, 'general'),
  paused: false,
  barHidden: false,
  settingsOpen: false,
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
  const p = new URLSearchParams({ dir: r.dir, theme: r.theme, view: r.view, scenario: r.scenario, page: r.page, lang: s.uiLang, target: s.target })
  history.replaceState(null, '', '?' + p.toString())
}
