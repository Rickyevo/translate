/* Pure settings model — no DOM, no store. Shared by the prototype, the app renderers and Electron main. */
import type { UiLangPref } from './i18n'
import type { Target } from './data/scenarios'

export type Theme = 'light' | 'dark'
export type View = 'desktop' | 'states' | 'settings' | 'components' | 'icons'
export type Density = 'comfortable' | 'compact'
export type LeadMode = 'auto' | 'request' | 'off'
export type IconId = 'underlay' | 'refraction' | 'overlap' | 'fold'
export type OrigMode = 'hover' | 'always' | 'never'
export type ThemePref = 'system' | 'light' | 'dark'
export type Page = 'overview' | 'general' | 'translation' | 'appearance' | 'privacy' | 'about'

/* ---------------- Translation services ---------------- */

export type ProviderId = 'openai' | 'claude' | 'gemini' | 'grok' | 'opencode-go' | 'deepseek' | 'custom'
/** Wire format: Chat Completions, Claude Messages, Gemini generateContent. */
export type Protocol = 'openai' | 'anthropic' | 'gemini'
export type AuthKind = 'bearer' | 'x-api-key' | 'x-goog-api-key' | 'header' | 'query' | 'none'
export interface ServiceCfg {
  endpoint?: string
  model?: string
  protocol?: Protocol
  auth?: AuthKind
  /** Header or query-parameter name for auth 'header' / 'query'. */
  authName?: string
}
/** Presets — keep in sync with backend/translate_backend/translate/providers.py PRESETS. */
export const PROVIDERS: Record<ProviderId, { label: string; protocol: Protocol; endpoint: string; model: string; auth: AuthKind[]; plan?: boolean }> = {
  openai: { label: 'OpenAI', protocol: 'openai', endpoint: 'https://api.openai.com/v1', model: 'gpt-6-luna', auth: ['bearer'] },
  claude: { label: 'Claude', protocol: 'anthropic', endpoint: 'https://api.anthropic.com', model: 'claude-opus-5-5', auth: ['x-api-key', 'bearer'] },
  gemini: { label: 'Gemini', protocol: 'gemini', endpoint: 'https://generativelanguage.googleapis.com/v1beta', model: 'gemini-flash-latest', auth: ['x-goog-api-key'] },
  grok: { label: 'Grok', protocol: 'openai', endpoint: 'https://api.x.ai/v1', model: 'grok-4.20', auth: ['bearer'] },
  'opencode-go': { label: 'OpenCode Go', protocol: 'openai', endpoint: 'https://opencode.ai/zen/go/v1', model: 'deepseek-v4-flash', auth: ['bearer'], plan: true },
  deepseek: { label: 'DeepSeek', protocol: 'openai', endpoint: 'https://api.deepseek.com', model: 'deepseek-v4-flash', auth: ['bearer'] },
  custom: { label: 'Custom', protocol: 'openai', endpoint: '', model: '', auth: ['bearer', 'x-api-key', 'header', 'query', 'none'] },
}
export const PROVIDER_IDS = Object.keys(PROVIDERS) as ProviderId[]

/** The effective service settings for a provider: preset defaults overlaid with the user's edits. */
export function serviceOf(s: Pick<Settings, 'provider' | 'services'>, id: ProviderId = s.provider) {
  const p = PROVIDERS[id]
  const c = s.services[id] ?? {}
  return {
    provider: id,
    endpoint: c.endpoint || p.endpoint,
    model: c.model || p.model,
    protocol: id === 'custom' ? (c.protocol ?? 'openai') : p.protocol,
    auth: c.auth && p.auth.includes(c.auth) ? c.auth : (id === 'custom' && c.auth ? c.auth : p.auth[0]),
    authName: c.authName ?? '',
  }
}

/* ---------------- Settings (saved vs. draft) ---------------- */

/** Which input method Translate follows: whichever is typing ('auto'), or only one. */
export type ImePref = 'auto' | 'wetype' | 'mspinyin'

export interface Settings {
  uiLang: UiLangPref
  ime: ImePref
  target: Target
  count: number
  autostart: boolean
  localDict: boolean
  provider: ProviderId
  services: Partial<Record<ProviderId, ServiceCfg>>
  /** Draft only: a key typed in the settings window. Main moves it to Windows Credential Manager on Save and
   *  never writes it to config.json or sends it back to any renderer. */
  apiKey: string
  timeout: number
  jsonMode: boolean
  theme: ThemePref
  textSize: number
  density: Density
  opacity: number
  offsetX: number
  offsetY: number
  showOriginal: OrigMode
  leadMode: LeadMode
  /** Place the panel clear of the IME's own window so it can take mouse input (see DESIGN §9). */
  clickable: boolean
  localOnly: boolean
  denylist: string[]
  shortcuts: { toggleBar: string; pause: string; settings: string }
}

export const DEFAULT_SETTINGS: Settings = {
  uiLang: 'system',
  ime: 'auto',
  target: 'en',
  count: 5,
  autostart: true,
  localDict: true,
  provider: 'openai',
  services: {},
  apiKey: '',
  timeout: 8,
  jsonMode: true,
  theme: 'system',
  textSize: 13,
  density: 'comfortable',
  opacity: 1,
  offsetX: 0,
  offsetY: 4,
  showOriginal: 'always',
  leadMode: 'auto',
  clickable: false,
  localOnly: false,
  denylist: ['KeePassXC.exe', 'mstsc.exe', '1Password.exe'],
  shortcuts: { toggleBar: 'Alt+0', pause: 'Ctrl+Alt+P', settings: 'Ctrl+Alt+O' },
}

/** Settings that preview live on the bar before saving. */
export const LIVE_KEYS: (keyof Settings)[] = ['theme', 'textSize', 'density', 'opacity', 'offsetX', 'offsetY', 'showOriginal', 'leadMode', 'clickable', 'uiLang']

/** What the bar currently renders with: live keys from draft, the rest from saved. */
export function effectiveSettings(s: { saved: Settings; draft: Settings }): Settings {
  const out = { ...s.saved }
  for (const k of LIVE_KEYS) (out as Record<string, unknown>)[k] = s.draft[k]
  return out
}

