import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { AppWindow, ArrowRight, Check, Eye, EyeOff, ExternalLink, FolderOpen, Pause, Monitor, Moon, Plus, Power, RotateCcw, Sun, Trash2, X } from 'lucide-react'
import { UI_LANGS, UI_LANG_NATIVE, systemLang, type UiLangPref } from '../i18n'
import { TARGETS, buildList, type Target } from '../data/scenarios'
import { effectiveSettings, useReview, useSettings, type Density, type LeadMode, type OrigMode, type ThemePref } from '../store'
import { PROVIDERS, PROVIDER_IDS, serviceOf, type AuthKind, type ImePref, type Protocol, type ProviderId, type ServiceCfg } from '../model'
import { bridge, useEngine } from './bridge'
import { DEFAULT_SHORTCUTS, SHORTCUT_IDS, capture, problem, type ShortcutId } from './shortcuts'
import { Button, IconButton, Kbd, Message, Segmented, Select, Shortcut, Slider, Switch, TextInput, cx } from '../ui/primitives'
import { Scope } from '../ui/scope'
import { Panel } from '../bars/Panel'
import { AppMark } from '../icons/AppMark'
import { PageHeader, Row, Section } from './parts'

function useDraft() {
  const draft = useSettings((s) => s.draft)
  const set = useSettings((s) => s.set)
  return [draft, set] as const
}

/* =========================================================== General */

export function GeneralPage() {
  const { t } = useTranslation()
  const [d, set] = useDraft()
  const sys = UI_LANG_NATIVE[systemLang()]
  const langOptions: { value: UiLangPref; label: string; lang?: string }[] = [
    { value: 'system', label: t('lang.systemWith', { name: sys }) },
    ...UI_LANGS.map((l) => ({ value: l as UiLangPref, label: UI_LANG_NATIVE[l], lang: l })),
  ]
  return (
    <>
      <PageHeader title={t('settings.general.title')} />
      <div className="flex flex-col gap-7">
        <Section>
          <Row
            label={t('settings.general.uiLang')}
            control={<Select label={t('settings.general.uiLang')} className="w-[184px]" value={d.uiLang} onValueChange={(v) => set('uiLang', v)} options={langOptions} />}
          />
          <Row
            label={t('settings.general.count')}
            desc={t('settings.general.countDesc', { n: d.count })}
            control={
              <Select
                label={t('settings.general.count')}
                className="w-[72px]"
                value={String(d.count)}
                onValueChange={(v) => set('count', Number(v))}
                options={[3, 4, 5, 6, 7, 8, 9].map((n) => ({ value: String(n), label: String(n) }))}
              />
            }
          />
          <Row label={t('settings.general.autostart')} desc={t('settings.general.autostartDesc')} control={<Switch label={t('settings.general.autostart')} checked={d.autostart} onCheckedChange={(v) => set('autostart', v)} />} />
        </Section>

        <Section title={t('settings.general.shortcuts')} desc={t('settings.general.shortcutsDesc')}>
          {SHORTCUT_IDS.map((k) => (
            <ShortcutRow key={k} k={k} />
          ))}
        </Section>

        <Section title={t('settings.general.panelKeys')}>
          <KeyRow label={t('settings.general.sc.insert')} keys={<KeyRange mods={['Alt']} />} />
          <KeyRow label={t('settings.general.sc.copy')} keys={<KeyRange mods={['Alt', 'Shift']} />} />
          <KeyRow label={t('settings.general.sc.preview')} keys={<Keys keys={['Alt', '`']} />} />
          <KeyRow label={t('settings.general.sc.step')} keys={<Keys keys={['Alt', '↑', '↓']} />} />
          <KeyRow label={t('settings.general.sc.scroll')} keys={<Keys keys={['Alt', 'PgUp', 'PgDn']} />} />
        </Section>
      </div>
    </>
  )
}

function Keys({ keys }: { keys: string[] }) {
  return (
    <span className="inline-flex items-center gap-0.5">
      {keys.map((k) => (
        <Kbd key={k}>{k}</Kbd>
      ))}
    </span>
  )
}

/** Alt+1 – 9 style ranges. */
function KeyRange({ mods }: { mods: string[] }) {
  return (
    <span className="inline-flex items-center gap-0.5">
      {mods.map((m) => (
        <Kbd key={m}>{m}</Kbd>
      ))}
      <Kbd>1</Kbd>
      <span className="px-0.5 text-12 text-fg-4">–</span>
      <Kbd>9</Kbd>
    </span>
  )
}

/** A compact read-only row: a label and its keys. */
function KeyRow({ label, keys }: { label: React.ReactNode; keys: React.ReactNode }) {
  return (
    <div className="flex min-h-10 items-center gap-3 px-4 py-2 text-13 text-fg-2">
      <span className="flex-1">{label}</span>
      {keys}
    </div>
  )
}

/** The keys of a customizable shortcut, or "Off". */
function ShortcutKeys({ accel }: { accel: string }) {
  const { t } = useTranslation()
  return accel ? <Shortcut keys={accel.replace('PageUp', 'PgUp').replace('PageDown', 'PgDn')} /> : <span className="text-12 text-fg-3">{t('settings.general.off')}</span>
}

/** Whether a saved shortcut is one Windows wouldn't give Translate (another app holds it). */
function useUnavailable(k: ShortcutId) {
  const saved = useSettings((s) => s.saved.shortcuts[k])
  const names = useEngine((e) => e.hotkeysUnavailable)
  return !!saved && !!names?.some((n) => n.toLowerCase() === saved.toLowerCase())
}

type ShortcutError = { key: string; keys?: string; other?: string }

/** One recorder at a time: starting another stops the current one. The host keeps Translate's shortcuts released
 *  from the first start to the last stop (a second row starting before the first one's cleanup must not bring them
 *  back early). */
let stopCurrent: (() => void) | null = null
let recorders = 0
const holdShortcuts = (on: boolean) => {
  recorders += on ? 1 : -1
  if (on ? recorders === 1 : recorders === 0) void bridge?.recordShortcut(on)
}

/**
 * Click the keys to record a new shortcut. Translate's own global shortcuts are released meanwhile (so the keys reach
 * this window); the combination is checked — its form, Windows and panel keys, the other shortcuts, then whether
 * another app holds it — and goes into the draft; Save registers it. Esc cancels, Backspace turns the shortcut off.
 */
function ShortcutRow({ k }: { k: ShortcutId }) {
  const { t } = useTranslation()
  const [d, set] = useDraft()
  const savedValue = useSettings((s) => s.saved.shortcuts[k])
  const unavailable = useUnavailable(k) && d.shortcuts[k] === savedValue
  const [rec, setRec] = useState(false)
  const [err, setErr] = useState<ShortcutError | null>(null)
  const value = d.shortcuts[k]
  const label = t(`settings.general.sc.${k}`)

  useEffect(() => {
    if (!rec) return
    let alive = true
    const stop = () => setRec(false)
    stopCurrent?.()
    stopCurrent = stop
    holdShortcuts(true)
    const plain = (e: KeyboardEvent) => !e.ctrlKey && !e.altKey && !e.shiftKey
    const on = async (e: KeyboardEvent) => {
      e.preventDefault()
      e.stopPropagation()
      if (e.repeat) return
      if (e.code === 'Escape' && plain(e)) return stop()
      const all = useSettings.getState().draft.shortcuts
      if ((e.code === 'Backspace' || e.code === 'Delete') && plain(e)) {
        set('shortcuts', { ...all, [k]: '' })
        setErr(null)
        return stop()
      }
      const c = capture(e)
      if ('pending' in c) return
      if ('invalid' in c) return setErr({ key: 'key' })
      const p = problem(c.accel, k, all)
      if (p) return setErr({ key: p.kind, keys: c.accel, other: p.kind === 'duplicate' ? t(`settings.general.sc.${p.other}`) : undefined })
      const free = bridge ? await bridge.shortcutAvailable(c.accel) : true
      if (!alive) return
      if (!free) return setErr({ key: 'taken', keys: c.accel })
      set('shortcuts', { ...useSettings.getState().draft.shortcuts, [k]: c.accel })
      setErr(null)
      stop()
    }
    window.addEventListener('keydown', on, true)
    window.addEventListener('blur', stop)
    return () => {
      alive = false
      window.removeEventListener('keydown', on, true)
      window.removeEventListener('blur', stop)
      if (stopCurrent === stop) stopCurrent = null
      holdShortcuts(false)
    }
  }, [rec, k, set, t])

  const desc = err ? (
    <span className="text-danger-text" role="alert">
      {t(`settings.general.err.${err.key}`, { keys: err.keys?.split('+').join(' + '), other: err.other })}
    </span>
  ) : rec ? (
    t('settings.general.recordHint')
  ) : unavailable ? (
    <span className="text-warning-text">{t('settings.general.unavailable')}</span>
  ) : undefined
  return (
    <Row
      label={label}
      desc={desc}
      control={
        <>
          {value !== DEFAULT_SHORTCUTS[k] && !rec && (
            <IconButton size="sm" label={t('settings.general.reset')} onClick={() => (set('shortcuts', { ...d.shortcuts, [k]: DEFAULT_SHORTCUTS[k] }), setErr(null))}>
              <RotateCcw className="size-3.5" />
            </IconButton>
          )}
          <button
            type="button"
            aria-label={t('settings.general.change', { name: label })}
            data-shortcut={k}
            onClick={() => (setErr(null), setRec((r) => !r))}
            className={cx(
              'focus-ring inline-flex h-[var(--ctl-h)] min-w-[136px] items-center justify-center gap-1 rounded-md px-2.5 transition-[box-shadow,background-color] duration-[var(--dur-1)]',
              rec
                ? 'bg-accent-soft text-12 font-medium text-accent-text shadow-[inset_0_0_0_1px_var(--c-accent)]'
                : cx('bg-raised hover:bg-hover', unavailable ? 'shadow-[inset_0_0_0_1px_var(--c-warning)]' : 'shadow-[var(--sh-control),inset_0_0_0_1px_var(--c-line)]'),
            )}
          >
            {rec ? t('settings.general.recording') : <ShortcutKeys accel={value} />}
          </button>
        </>
      }
    />
  )
}

/* =========================================================== Translation */

type TestState = { s: 'idle' } | { s: 'testing' } | { s: 'ok'; ms: number } | { s: 'err'; key: string; status?: number; detail?: string }

const AUTH_LABEL: Record<AuthKind, string> = {
  bearer: 'bearer',
  'x-api-key': 'xApiKey',
  'x-goog-api-key': 'xGoogApiKey',
  header: 'header',
  query: 'query',
  none: 'none',
}

export function TranslationPage() {
  const { t } = useTranslation()
  const [d, set] = useDraft()
  const [showKey, setShowKey] = useState(false)
  const [test, setTest] = useState<TestState>({ s: 'idle' })
  const [keys, setKeys] = useState<Partial<Record<ProviderId, boolean>>>({})
  const [models, setModels] = useState<{ provider: ProviderId; list: string[] } | null>(null)
  const [loadingModels, setLoadingModels] = useState(false)
  const pid = d.provider
  const preset = PROVIDERS[pid]
  const svc = serviceOf(d)
  const cfg = d.services[pid] ?? {}
  const urlBad = !/^https?:\/\//.test(svc.endpoint)
  const stored = !!keys[pid]
  const needsKey = svc.auth !== 'none'

  const typing = !!d.apiKey
  useEffect(() => {
    if (!typing) bridge?.keys().then(setKeys) // also after Save hands a typed key to the vault
  }, [typing])
  useEffect(() => setTest({ s: 'idle' }), [pid])

  const patch = (p: ServiceCfg) => set('services', { ...d.services, [pid]: { ...cfg, ...p } })
  const keyLabel = preset.plan ? t('settings.translation.planKey') : svc.auth === 'bearer' && pid === 'claude' ? t('settings.translation.authToken') : t('settings.translation.apiKey')

  const run = async () => {
    if (needsKey && !d.apiKey.trim() && !stored) return setTest({ s: 'err', key: 'noKey' })
    if (urlBad) return setTest({ s: 'err', key: 'badUrl' })
    setTest({ s: 'testing' })
    if (!bridge) {
      window.setTimeout(() => setTest(/bad|invalid/i.test(d.apiKey) ? { s: 'err', key: 'auth' } : { s: 'ok', ms: 380 + Math.round(Math.random() * 120) }), 900)
      return
    }
    const r = await bridge.test({ ...svc, jsonMode: d.jsonMode }, d.apiKey.trim())
    setTest(r.ok ? { s: 'ok', ms: r.ms } : { s: 'err', key: r.error, status: r.status, detail: r.detail })
  }

  const loadModels = async () => {
    if (!bridge) return
    setLoadingModels(true)
    const r = await bridge.models({ ...svc, jsonMode: d.jsonMode }, d.apiKey.trim())
    setLoadingModels(false)
    if (r.ok && r.models?.length) setModels({ provider: pid, list: r.models })
    else setTest({ s: 'err', key: r.error ?? 'http', status: r.status, detail: r.detail })
  }

  const off = d.localOnly

  return (
    <>
      <PageHeader title={t('settings.translation.title')} />
      <div className="flex flex-col gap-7">
        <Section title={t('settings.translation.service')} desc={t('settings.translation.serviceDesc')}>
          {off && (
            <div className={'px-4 py-3'}>
              <Message tone="info">{t('bar.status.localOnlyLong')}</Message>
            </div>
          )}
          <Row
            label={t('settings.translation.provider')}
            disabled={off}
            control={
              <Select<ProviderId>
                label={t('settings.translation.provider')}
                className="w-[184px]"
                value={pid}
                onValueChange={(v) => (set('provider', v), set('apiKey', ''))}
                options={PROVIDER_IDS.map((id) => ({ value: id, label: id === 'custom' ? t('settings.translation.custom') : PROVIDERS[id].label, hint: keys[id] ? t('settings.translation.keySavedShort') : undefined }))}
              />
            }
          />
          {pid === 'custom' && (
            <Row
              label={t('settings.translation.format')}
              desc={t('settings.translation.formatDesc')}
              disabled={off}
              control={
                <Segmented<Protocol>
                  label={t('settings.translation.format')}
                  value={svc.protocol}
                  onValueChange={(v) => patch({ protocol: v })}
                  options={[
                    { value: 'openai', label: t('settings.translation.formats.openai') },
                    { value: 'anthropic', label: 'Claude' },
                    { value: 'gemini', label: 'Gemini' },
                  ]}
                />
              }
            />
          )}
          <Row label={t('settings.translation.endpoint')} htmlFor="ep" stack disabled={off}>
            <TextInput
              id="ep"
              value={cfg.endpoint ?? preset.endpoint}
              placeholder={preset.endpoint || 'https://…/v1'}
              invalid={test.s === 'err' && test.key === 'badUrl'}
              onChange={(e) => patch({ endpoint: e.target.value })}
              spellCheck={false}
            />
          </Row>
          {preset.auth.length > 1 && (
            <Row
              label={t('settings.translation.auth')}
              disabled={off}
              control={
                <Select<AuthKind>
                  label={t('settings.translation.auth')}
                  className="w-[184px]"
                  value={svc.auth}
                  onValueChange={(v) => patch({ auth: v })}
                  options={preset.auth.map((a) => ({ value: a, label: t(`settings.translation.authKind.${AUTH_LABEL[a]}`) }))}
                />
              }
            />
          )}
          {(svc.auth === 'header' || svc.auth === 'query') && (
            <Row label={svc.auth === 'header' ? t('settings.translation.headerName') : t('settings.translation.paramName')} htmlFor="an" stack disabled={off}>
              <TextInput id="an" mono value={cfg.authName ?? ''} placeholder={svc.auth === 'header' ? 'api-key' : 'key'} onChange={(e) => patch({ authName: e.target.value })} spellCheck={false} />
            </Row>
          )}
          {needsKey && (
            <Row label={keyLabel} desc={stored && !d.apiKey ? t('settings.translation.keySaved') : t('settings.translation.apiKeyDesc')} htmlFor="key" stack disabled={off}>
              <TextInput
                id="key"
                mono
                type={showKey ? 'text' : 'password'}
                value={d.apiKey}
                placeholder={stored ? '••••••••••••' : ''}
                invalid={test.s === 'err' && (test.key === 'auth' || test.key === 'noKey')}
                onChange={(e) => set('apiKey', e.target.value)}
                spellCheck={false}
                autoComplete="off"
                suffix={
                  <IconButton size="sm" label={showKey ? t('settings.translation.hide') : t('settings.translation.show')} onClick={() => setShowKey((v) => !v)}>
                    {showKey ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
                  </IconButton>
                }
              />
            </Row>
          )}
          <div className={cx('grid grid-cols-[1fr_120px] gap-x-4', 'px-4 py-3', off && 'opacity-50')}>
            <div className="flex min-w-0 flex-col gap-2">
              <span className="flex items-center justify-between text-13 font-medium text-fg">
                <label htmlFor="model">{t('settings.translation.model')}</label>
                {bridge && (
                  <Button size="sm" variant="ghost" disabled={off || loadingModels} onClick={loadModels}>
                    {loadingModels ? t('settings.translation.loadingModels') : t('settings.translation.loadModels')}
                  </Button>
                )}
              </span>
              <TextInput id="model" value={cfg.model ?? preset.model} placeholder={preset.model} onChange={(e) => patch({ model: e.target.value })} spellCheck={false} />
              {models && models.provider === pid && (
                <Select<string>
                  label={t('settings.translation.models')}
                  className="w-full"
                  value={models.list.includes(svc.model) ? svc.model : ''}
                  onValueChange={(v) => patch({ model: v })}
                  options={models.list.map((m) => ({ value: m, label: m }))}
                />
              )}
            </div>
            <label className="flex flex-col gap-2">
              <span className="flex h-6 items-center text-13 font-medium text-fg">{t('settings.translation.timeout')}</span>
              <TextInput
                className="tnum"
                inputMode="numeric"
                value={String(d.timeout)}
                onChange={(e) => set('timeout', Number(e.target.value.replace(/\D/g, '')) || 0)}
                suffix={<span className="pr-2 text-12 text-fg-3">{t('settings.translation.seconds')}</span>}
              />
            </label>
          </div>
          {/* Presets know whether their service takes JSON output; only a custom service needs the choice. */}
          {pid === 'custom' && svc.protocol === 'openai' && (
            <Row label={t('settings.translation.jsonMode')} desc={t('settings.translation.jsonModeDesc')} disabled={off} control={<Switch label={t('settings.translation.jsonMode')} checked={d.jsonMode} onCheckedChange={(v) => set('jsonMode', v)} />} />
          )}
          <div className={cx('flex flex-col gap-2.5', 'px-4 py-3.5')}>
            <div className="flex items-center gap-3">
              <Button onClick={run} disabled={test.s === 'testing' || off}>
                {test.s === 'testing' ? t('settings.translation.testing') : t('settings.translation.test')}
              </Button>
              {test.s === 'ok' && (
                <span className="anim-fade inline-flex items-center gap-1.5 text-12 text-success-text">
                  <Check className="size-3.5" strokeWidth={2.25} />
                  {t('settings.translation.ok', { model: svc.model, ms: test.ms })}
                </span>
              )}
            </div>
            {test.s === 'err' && (
              <Message tone="danger" className="anim-fade">
                {t(`settings.translation.err.${test.key}`, { defaultValue: t('settings.translation.err.http') })}
                {(test.status || test.detail) && (
                  // The service's own words (status + error type/message) — what's needed to tell an endpoint,
                  // model, request-format or key problem apart.
                  <span className="mt-1 block break-words font-mono text-12 opacity-80">
                    {t('settings.translation.serviceSaid', { detail: [test.status ? `HTTP ${test.status}` : '', test.detail].filter(Boolean).join(' · ') })}
                  </span>
                )}
              </Message>
            )}
          </div>
        </Section>

        <Section>
          <Row label={t('settings.translation.localDict')} desc={t('settings.translation.localDictDesc')} control={<Switch label={t('settings.translation.localDict')} checked={d.localDict} onCheckedChange={(v) => set('localDict', v)} />} />
        </Section>
      </div>
    </>
  )
}

/* =========================================================== Appearance */

export function AppearancePage() {
  const { t } = useTranslation()
  const [d, set] = useDraft()
  const orig = d.showOriginal
  return (
    <>
      <PageHeader title={t('settings.appearance.title')} />
      <div className="flex flex-col gap-7">
        <BarPreview />
        <Section>
          <Row
            label={t('settings.appearance.theme')}
            control={
              <Segmented<ThemePref>
                label={t('settings.appearance.theme')}
                value={d.theme}
                onValueChange={(v) => set('theme', v)}
                options={[
                  { value: 'system', label: t('settings.appearance.themeSystem'), icon: <Monitor className="size-3.5" /> },
                  { value: 'light', label: t('settings.appearance.themeLight'), icon: <Sun className="size-3.5" /> },
                  { value: 'dark', label: t('settings.appearance.themeDark'), icon: <Moon className="size-3.5" /> },
                ]}
              />
            }
          />
          <Row label={t('settings.appearance.textSize')} control={<Slider label={t('settings.appearance.textSize')} value={d.textSize} min={12} max={16} step={1} onValueChange={(v) => set('textSize', v)} format={(v) => `${v} px`} />} />
          <Row
            label={t('settings.appearance.density')}
            desc={t('settings.appearance.densityDesc')}
            control={
              <Segmented<Density>
                label={t('settings.appearance.density')}
                value={d.density}
                onValueChange={(v) => set('density', v)}
                options={(['comfortable', 'compact'] as const).map((v) => ({ value: v, label: t(`settings.appearance.dens.${v}`) }))}
              />
            }
          />
          <Row label={t('settings.appearance.opacity')} control={<Slider label={t('settings.appearance.opacity')} value={d.opacity} min={0.9} max={1} step={0.01} onValueChange={(v) => set('opacity', v)} format={(v) => `${Math.round(v * 100)}%`} />} />
          <Row
            label={t('settings.appearance.offset')}
            desc={t('settings.appearance.offsetDesc')}
            control={
              <>
                <Stepper label="X" value={d.offsetX} onChange={(v) => set('offsetX', v)} />
                <Stepper label="Y" value={d.offsetY} onChange={(v) => set('offsetY', v)} />
              </>
            }
          />
          <Row
            label={t('settings.appearance.clickable')}
            desc={t('settings.appearance.clickableDesc')}
            control={<Switch label={t('settings.appearance.clickable')} checked={d.clickable} onCheckedChange={(v) => set('clickable', v)} />}
          />
          <Row
            label={t('settings.appearance.lead')}
            desc={t('settings.appearance.leadDesc')}
            control={
              <Segmented<LeadMode>
                label={t('settings.appearance.lead')}
                value={d.leadMode}
                onValueChange={(v) => set('leadMode', v)}
                options={(['auto', 'request', 'off'] as const).map((v) => ({ value: v, label: t(`settings.appearance.leadMode.${v}`) }))}
              />
            }
          />
          <Row
            label={t('settings.appearance.showOriginal')}
            desc={t('settings.appearance.showOriginalDesc')}
            control={
              <Segmented<OrigMode>
                label={t('settings.appearance.showOriginal')}
                value={orig}
                onValueChange={(v) => set('showOriginal', v)}
                options={(['hover', 'always', 'never'] as const).map((v) => ({ value: v, label: t(`settings.appearance.orig.${v}`) }))}
              />
            }
          />
        </Section>
      </div>
    </>
  )
}

function Stepper({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <span className="inline-flex items-center gap-1.5">
    <span className="text-12 text-fg-3">{label}</span>
    <TextInput
      aria-label={label}
      wrapClassName="w-[64px]"
      className="tnum pl-0 text-right"
      value={String(value)}
      onChange={(e) => {
        const n = Number(e.target.value.replace(/[^\d-]/g, ''))
        if (!Number.isNaN(n)) onChange(Math.max(-40, Math.min(40, n)))
      }}
      onKeyDown={(e) => {
        if (e.key === 'ArrowUp') (e.preventDefault(), onChange(Math.min(40, value + 1)))
        if (e.key === 'ArrowDown') (e.preventDefault(), onChange(Math.max(-40, value - 1)))
      }}
      suffix={<span className="pr-1.5 text-12 text-fg-4">px</span>}
    />
    </span>
  )
}

/** Actual-size preview against a busy and a plain backdrop. */
function BarPreview() {
  const { t } = useTranslation()
  const st = useSettings()
  const s = effectiveSettings(st)
  const reviewTheme = useReview((r) => r.theme)
  const theme = s.theme === 'system' ? reviewTheme : s.theme
  const list = useMemo(() => {
    const l = buildList('short', s.target, s.count)
    return { ...l, items: l.items.map((it) => (it.n === 4 ? { n: 4, text: it.text, state: 'loading' as const } : it)) }
  }, [s.target, s.count])
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between px-0.5">
        <h3 className="text-14 font-semibold text-fg">{t('settings.appearance.preview')}</h3>
        <span className="text-12 text-fg-3">{t('settings.appearance.previewDesc')}</span>
      </div>
      <div
        className="relative flex overflow-hidden rounded-xl shadow-[inset_0_0_0_1px_var(--c-line-soft)]"
        style={{
          paddingBottom: 20,
          background:
            'repeating-linear-gradient(135deg, oklch(0.62 0.05 240) 0 14px, oklch(0.7 0.06 200) 14px 28px), linear-gradient(90deg, oklch(0.8 0.05 90), oklch(0.5 0.08 280))',
          backgroundBlendMode: 'soft-light',
        }}
      >
        <div className="relative ml-5 mt-5 flex flex-col items-start" style={{ gap: s.offsetY }}>
          <FakeImeWindow pinyin={list.pinyin} items={list.items.map((i) => i.text)} />
          <div style={{ marginLeft: s.offsetX }}>
            <Scope theme={theme}>
              <Panel list={list} s={s} paused={false} />
            </Scope>
          </div>
        </div>
      </div>
    </div>
  )
}

/** Approximation of the WeChat IME candidate window (light skin). */
export function FakeImeWindow({ pinyin, items, compact }: { pinyin: string; items: string[]; compact?: boolean }) {
  return (
    <div
      className="inline-flex flex-col rounded-[8px] bg-white text-[oklch(0.25_0_0)] shadow-[0_0_0_1px_oklch(0_0_0/0.1),0_6px_16px_oklch(0_0_0/0.15)]"
      style={{ fontFamily: '"Microsoft YaHei UI", "Microsoft YaHei", sans-serif' }}
      lang="zh-CN"
    >
      <div className="px-3 pt-1.5 text-[13px] leading-[18px] text-[oklch(0.45_0_0)]">{pinyin.length > 34 ? pinyin.slice(0, 34) + '…' : pinyin}</div>
      <div className={cx('flex items-center gap-3 px-3 pb-2 pt-0.5', compact ? 'text-[15px]' : 'text-[16px]')}>
        {items.slice(0, 5).map((c, i) => (
          <span key={i} className="flex items-baseline gap-1 whitespace-nowrap">
            <span className="text-[12px] text-[oklch(0.55_0_0)]">{i + 1}.</span>
            <span className={i === 0 ? 'text-[oklch(0.5_0.17_150)]' : ''}>{c.length > 8 ? c.slice(0, 8) + '…' : c}</span>
          </span>
        ))}
      </div>
    </div>
  )
}

/* =========================================================== Privacy */

export function PrivacyPage() {
  const { t } = useTranslation()
  const [d, set] = useDraft()
  const [adding, setAdding] = useState('')
  const [cleared, setCleared] = useState(false)
  const [cache, setCache] = useState<{ count: number; bytes: number } | null>(bridge ? null : { count: 2318, bytes: 412 * 1024 })
  useEffect(() => {
    bridge?.cacheStats().then(setCache)
  }, [])
  const size = (b: number) => (b < 1024 ? `${b} B` : b < 1024 * 1024 ? `${Math.round(b / 1024)} KB` : `${(b / 1024 / 1024).toFixed(1)} MB`)
  const pad = 'px-4 py-3'
  return (
    <>
      <PageHeader title={t('settings.privacy.title')} />
      <div className="flex flex-col gap-7">
        <Section>
          <Row label={t('settings.privacy.localOnly')} desc={t('settings.privacy.localOnlyDesc')} control={<Switch label={t('settings.privacy.localOnly')} checked={d.localOnly} onCheckedChange={(v) => set('localOnly', v)} />} />
        </Section>

        <Section title={t('settings.privacy.denylist')} desc={t('settings.privacy.denylistDesc')}>
          {d.denylist.map((app) => (
            <div key={app} className={cx('group flex items-center gap-2.5', 'h-11 px-4')}>
              <AppWindow className="size-4 shrink-0 text-fg-3" strokeWidth={1.75} />
              <span className="flex-1 text-13 text-fg">{app}</span>
              <IconButton size="sm" label={t('settings.privacy.remove')} className="opacity-0 focus-visible:opacity-100 group-hover:opacity-100" onClick={() => set('denylist', d.denylist.filter((x) => x !== app))}>
                <X className="size-3.5" />
              </IconButton>
            </div>
          ))}
          <form
            className={cx('flex items-center gap-2', pad)}
            onSubmit={(e) => {
              e.preventDefault()
              const v = adding.trim()
              if (v && !d.denylist.includes(v)) set('denylist', [...d.denylist, v])
              setAdding('')
            }}
          >
            <TextInput wrapClassName="flex-1" placeholder={t('settings.privacy.addPlaceholder')} value={adding} onChange={(e) => setAdding(e.target.value)} />
            <Button type="submit" disabled={!adding.trim()}>
              <Plus className="size-3.5" />
              {t('settings.privacy.add')}
            </Button>
          </form>
        </Section>

        <Section title={t('settings.privacy.storage')}>
          <Row label={t('settings.privacy.storeKey')} desc={t('settings.privacy.storeKeyVal')} />
          <Row
            label={t('settings.privacy.cache')}
            desc={cleared ? t('settings.privacy.cleared') : cache ? t('settings.privacy.cacheInfo', { count: cache.count, size: size(cache.bytes) }) : '…'}
            control={
              <Button variant="danger" disabled={cleared || cache?.count === 0} onClick={() => (bridge ? bridge.clearCache().then(setCache) : null, setCleared(true))}>
                <Trash2 className="size-3.5" />
                {t('settings.privacy.clear')}
              </Button>
            }
          />
          <Row
            label={t('settings.privacy.logs')}
            desc={t('settings.privacy.logsDesc')}
            control={
              <Button onClick={() => bridge?.openLogs()}>
                <FolderOpen className="size-3.5" />
                {t('settings.privacy.openLogs')}
              </Button>
            }
          />
        </Section>
      </div>
    </>
  )
}

/* =========================================================== About */

export function AboutPage({ onQuit }: { onQuit: () => void }) {
  const { t } = useTranslation()
  const version = useReview((r) => r.version)
  return (
    <>
      <div className="mb-6 flex items-center gap-3.5">
        <AppMark size={48} />
        <div>
          <h2 className="text-22 font-semibold tracking-[-0.01em] text-fg">{t('app.name')}</h2>
          <p className="text-13 text-fg-3 tnum" data-version>
            {t('settings.about.version', { v: version })}
          </p>
        </div>
      </div>
      <div className="flex flex-col gap-7">
        <Section>
          <LinkRow label={t('settings.about.updates')} onClick={() => bridge?.openLink('releases')} />
          <LinkRow label={t('settings.about.report')} onClick={() => bridge?.openLink('issues')} />
          <LinkRow label={t('settings.about.notices')} onClick={() => bridge?.openLink('notices')} />
          {/* Required attribution (CC BY-SA 4.0) for the local dictionary. */}
          <div className="flex min-h-11 items-center justify-between gap-6 px-4 py-2.5 text-13">
            <span className="text-fg-2">{t('settings.about.dict')}</span>
            <span className="text-fg">CC-CEDICT · CC BY-SA 4.0</span>
          </div>
        </Section>
        <Section>
          <Row
            label={t('settings.about.quit')}
            desc={t('settings.about.quitDesc')}
            control={
              <Button variant="danger" onClick={onQuit}>
                <Power className="size-3.5" />
                {t('settings.about.quit')}
              </Button>
            }
          />
        </Section>
      </div>
    </>
  )
}

/** A row that opens a page or file outside Settings. */
function LinkRow({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="focus-ring group flex min-h-11 w-full items-center gap-3 px-4 py-2.5 text-left text-13 text-fg-2 hover:bg-hover hover:text-fg">
      <span className="flex-1">{label}</span>
      <ExternalLink className="size-3.5 text-fg-4 group-hover:text-fg-3" />
    </button>
  )
}

/* =========================================================== Overview */

type ImeId = 'wetype' | 'mspinyin'
const IMES: ImeId[] = ['wetype', 'mspinyin']
const imeOn = (pref: ImePref, id: ImeId) => pref === 'auto' || pref === id

/**
 * What an input method's row says. The engine's state is per adapter ("connected" means Translate is attached and
 * ready, not that Windows currently has that input method selected); a draft change shows until it's saved.
 */
function imeStatus(id: ImeId, draft: ImePref, saved: ImePref, state: string | undefined): { key: string; tone: 'ok' | 'muted' | 'warn' } {
  if (!imeOn(draft, id)) return { key: 'off', tone: 'muted' }
  if (!imeOn(saved, id)) return { key: 'afterSave', tone: 'muted' }
  if (state === 'connected') return { key: 'ready', tone: 'ok' }
  if (state === 'failed') return { key: 'failed', tone: 'warn' }
  if (state === 'waiting') return { key: id === 'wetype' ? 'notRunning' : 'starting', tone: 'muted' }
  return { key: 'starting', tone: 'muted' }
}

export function OverviewPage({ go }: { go: (p: 'general' | 'translation') => void }) {
  const { t } = useTranslation()
  const [d, set] = useDraft()
  const savedIme = useSettings((s) => s.saved.ime)
  const saved = useSettings((s) => s.saved)
  const paused = useReview((r) => r.paused)
  const setp = useReview((r) => r.setp)
  const states = useEngine((e) => e.imeStates) ?? {}
  const unavailable = useEngine((e) => e.hotkeysUnavailable) ?? []
  const [keys, setKeys] = useState<Partial<Record<ProviderId, boolean>>>(bridge ? {} : { openai: true })
  useEffect(() => {
    bridge?.keys().then(setKeys)
  }, [saved])
  // The service line describes what is saved (what translates right now).
  const svc = serviceOf(saved)
  const serviceReady = !!keys[saved.provider] || svc.auth === 'none'
  const serviceName = saved.provider === 'custom' ? t('settings.translation.custom') : PROVIDERS[saved.provider].label
  const toggleIme = (id: ImeId, on: boolean) => {
    const next = IMES.filter((x) => (x === id ? on : imeOn(d.ime, x)))
    if (next.length) set('ime', next.length === 2 ? 'auto' : next[0])
  }
  const sc = saved.shortcuts
  const taken = (a: string) => !!a && unavailable.some((n) => n.toLowerCase() === a.toLowerCase())

  return (
    <>
      {/* The status card is this page's headline (the sidebar names the page). */}
      <h2 className="sr-only">{t('settings.overview.title')}</h2>
      <div className="flex flex-col gap-5 pt-2">
        <Section>
          <div className="flex items-center gap-3 px-4 py-3.5">
            <span className={cx('inline-flex size-9 shrink-0 items-center justify-center rounded-lg', paused ? 'bg-sunken text-fg-3' : 'bg-accent-soft text-accent-text')}>
              {paused ? <Pause className="size-4" /> : <Check className="size-4" strokeWidth={2.25} />}
            </span>
            <div className="min-w-0 flex-1">
              <div className="text-14 font-semibold text-fg">{paused ? t('settings.overview.paused') : t('settings.overview.on')}</div>
              <div className="flex flex-wrap items-center gap-x-2 text-12 text-fg-3" data-service-line>
                {saved.localOnly ? (
                  t('settings.overview.localOnly')
                ) : serviceReady ? (
                  <span className="truncate">{t('settings.overview.via', { service: serviceName, model: svc.model })}</span>
                ) : (
                  <>
                    {t('settings.overview.dictOnly')}
                    <button type="button" className="focus-ring inline-flex items-center gap-0.5 rounded-xs font-medium text-accent-text hover:underline" onClick={() => go('translation')}>
                      {t('settings.overview.setUp')}
                      <ArrowRight className="size-3" />
                    </button>
                  </>
                )}
              </div>
            </div>
            {/* On while translating, off when paused: the switch states what is happening. */}
            <Switch label={t('settings.overview.toggle')} checked={!paused} onCheckedChange={(v) => setp({ paused: !v })} />
          </div>
          <Row
            label={t('settings.general.target')}
            control={
              <Select<Target>
                label={t('settings.general.target')}
                className="w-[184px]"
                value={d.target}
                onValueChange={(v) => set('target', v)}
                options={TARGETS.map((x) => ({ value: x.id, label: x.native, lang: x.id }))}
              />
            }
          />
        </Section>

        <Section title={t('settings.overview.imes')}>
          {IMES.map((id) => {
            const st = imeStatus(id, d.ime, savedIme, states[id])
            const on = imeOn(d.ime, id)
            const name = t(id === 'wetype' ? 'settings.about.imeVal' : 'settings.about.imeMsPinyin')
            return (
              <Row
                key={id}
                label={name}
                control={
                  <>
                    <span data-ime={id} data-state={st.key} className={cx('text-12', st.tone === 'ok' ? 'text-success-text' : st.tone === 'warn' ? 'text-warning-text' : 'text-fg-3')}>
                      {t(`settings.overview.ime.${st.key}`)}
                    </span>
                    {/* At least one stays on: the last one's switch can't be turned off (pause is the way to stop). */}
                    <Switch label={name} checked={on} disabled={on && !IMES.some((x) => x !== id && imeOn(d.ime, x))} onCheckedChange={(v) => toggleIme(id, v)} />
                  </>
                }
              />
            )
          })}
        </Section>

        <Section
          title={t('settings.general.shortcuts')}
          desc={t('settings.overview.keysDesc')}
          aside={
            <Button size="sm" variant="ghost" onClick={() => go('general')}>
              {t('settings.overview.customize')}
            </Button>
          }
        >
          <KeyRow label={t('settings.general.sc.insert')} keys={<KeyRange mods={['Alt']} />} />
          {(['pause', 'settings'] as const).map((k) => (
            <KeyRow
              key={k}
              label={
                <span className="flex flex-col">
                  {t(`settings.general.sc.${k}`)}
                  {taken(sc[k]) && <span className="text-12 text-warning-text">{t('settings.overview.keyTaken')}</span>}
                </span>
              }
              keys={<ShortcutKeys accel={sc[k]} />}
            />
          ))}
        </Section>
      </div>
    </>
  )
}
