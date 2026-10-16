import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ArrowRight, Check, Copy, Eye, EyeOff, FolderOpen, Pause, Monitor, Moon, Plus, Power, Sun, Trash2, X, Database, Cloud, BookOpen } from 'lucide-react'
import { UI_LANGS, UI_LANG_NATIVE, systemLang, type UiLangPref } from '../i18n'
import { TARGETS, buildList, type Target } from '../data/scenarios'
import { effectiveSettings, useReview, useSettings, type Density, type LeadMode, type OrigMode, type Settings, type ThemePref } from '../store'
import { PROVIDERS, PROVIDER_IDS, serviceOf, type AuthKind, type Protocol, type ProviderId, type ServiceCfg } from '../model'
import { bridge } from './bridge'
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
      <PageHeader title={t('settings.general.title')} desc={t('settings.general.desc')} />
      <div className="flex flex-col gap-7">
        <Section title={t('settings.general.language')}>
          <Row
            label={t('settings.general.uiLang')}
            desc={t('settings.general.uiLangDesc')}
            control={<Select label={t('settings.general.uiLang')} className="w-[184px]" value={d.uiLang} onValueChange={(v) => set('uiLang', v)} options={langOptions} />}
          />
          <Row
            label={t('settings.general.target')}
            desc={t('settings.general.targetDesc')}
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
        </Section>

        <Section title={t('settings.general.startup')}>
          <Row label={t('settings.general.autostart')} desc={t('settings.general.autostartDesc')} control={<Switch label={t('settings.general.autostart')} checked={d.autostart} onCheckedChange={(v) => set('autostart', v)} />} />
        </Section>

        <Section title={t('settings.general.shortcuts')} desc={t('settings.general.shortcutsDesc')}>
          <Row
            label={t('settings.general.sc.insert')}
            control={
              <span className="inline-flex items-center gap-0.5">
                <Kbd>Alt</Kbd>
                <Kbd>1</Kbd>
                <span className="px-0.5 text-12 text-fg-4">–</span>
                <Kbd>9</Kbd>
              </span>
            }
          />
          <Row
            label={t('settings.general.sc.copy')}
            control={
              <span className="inline-flex items-center gap-0.5">
                <Kbd>Alt</Kbd>
                <Kbd>Shift</Kbd>
                <Kbd>1</Kbd>
                <span className="px-0.5 text-12 text-fg-4">–</span>
                <Kbd>9</Kbd>
              </span>
            }
          />
          <FixedKeys label={t('settings.general.sc.preview')} keys={['Alt', '`']} />
          <FixedKeys label={t('settings.general.sc.step')} keys={['Alt', '↑', '↓']} />
          <FixedKeys label={t('settings.general.sc.scroll')} keys={['Alt', 'PgUp', 'PgDn']} />
          <ShortcutRow k="toggleBar" />
          <ShortcutRow k="pause" />
          <ShortcutRow k="settings" />
        </Section>
      </div>
    </>
  )
}

function FixedKeys({ label, keys }: { label: string; keys: string[] }) {
  return (
    <Row
      label={label}
      control={
        <span className="inline-flex items-center gap-0.5">
          {keys.map((k) => (
            <Kbd key={k}>{k}</Kbd>
          ))}
        </span>
      }
    />
  )
}

function ShortcutRow({ k }: { k: keyof Settings['shortcuts'] }) {
  const { t } = useTranslation()
  const [d, set] = useDraft()
  const [rec, setRec] = useState(false)
  useEffect(() => {
    if (!rec) return
    const on = (e: KeyboardEvent) => {
      e.preventDefault()
      if (['Control', 'Alt', 'Shift', 'Meta'].includes(e.key)) return
      if (e.key === 'Escape') return setRec(false)
      const parts = [e.ctrlKey && 'Ctrl', e.altKey && 'Alt', e.shiftKey && 'Shift', e.key.length === 1 ? e.key.toUpperCase() : e.key].filter(Boolean)
      if (parts.length >= 2) {
        set('shortcuts', { ...d.shortcuts, [k]: parts.join('+') })
        setRec(false)
      }
    }
    window.addEventListener('keydown', on, true)
    return () => window.removeEventListener('keydown', on, true)
  }, [rec, d.shortcuts, k, set])
  return (
    <Row
      label={t(`settings.general.sc.${k}`)}
      control={
        <>
          {rec ? (
            <span className="rounded-xs px-1.5 text-12 text-accent-text shadow-[inset_0_0_0_1px_var(--c-accent)]">{t('settings.general.recording')}</span>
          ) : (
            <Shortcut keys={d.shortcuts[k]} />
          )}
          <Button size="sm" variant="ghost" onClick={() => setRec((r) => !r)}>
            {t('settings.general.change')}
          </Button>
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

  const step = (icon: React.ReactNode, label: string) => (
    <span className="inline-flex h-6 items-center gap-1.5 rounded-sm bg-sunken px-2 text-12 text-fg-2 shadow-[inset_0_0_0_1px_var(--c-line-soft)]">
      {icon}
      {label}
    </span>
  )
  const off = d.localOnly

  return (
    <>
      <PageHeader title={t('settings.translation.title')} desc={t('settings.translation.desc')} />
      <div className="flex flex-col gap-7">
        <Section title={t('settings.translation.order')} desc={t('settings.translation.orderDesc')}>
          <div className={cx('flex flex-wrap items-center gap-1.5', 'px-4 py-3.5')}>
            {step(<Database className="size-3 text-fg-3" />, t('bar.source.cache'))}
            <ArrowRight className="size-3 text-fg-4" />
            {step(<BookOpen className="size-3 text-fg-3" />, t('bar.source.dict'))}
            <ArrowRight className="size-3 text-fg-4" />
            {step(<Cloud className="size-3 text-fg-3" />, t('bar.source.ai'))}
          </div>
          <Row label={t('settings.translation.localDict')} desc={t('settings.translation.localDictDesc')} control={<Switch label={t('settings.translation.localDict')} checked={d.localDict} onCheckedChange={(v) => set('localDict', v)} />} />
        </Section>

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
              <span className={'flex h-6 items-end text-13 font-medium text-fg'}>{t('settings.translation.timeout')}</span>
              <TextInput
                className="tnum"
                inputMode="numeric"
                value={String(d.timeout)}
                onChange={(e) => set('timeout', Number(e.target.value.replace(/\D/g, '')) || 0)}
                suffix={<span className="pr-2 text-12 text-fg-3">{t('settings.translation.seconds')}</span>}
              />
            </label>
          </div>
          {svc.protocol === 'openai' && (
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
      <PageHeader title={t('settings.appearance.title')} desc={t('settings.appearance.desc')} />
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
      <PageHeader title={t('settings.privacy.title')} desc={t('settings.privacy.desc')} />
      <div className="flex flex-col gap-7">
        <Section>
          <Row label={t('settings.privacy.localOnly')} desc={t('settings.privacy.localOnlyDesc')} control={<Switch label={t('settings.privacy.localOnly')} checked={d.localOnly} onCheckedChange={(v) => set('localOnly', v)} />} />
        </Section>

        <Section title={t('settings.privacy.denylist')} desc={t('settings.privacy.denylistDesc')}>
          {d.denylist.map((app) => (
            <div key={app} className={cx('group flex items-center gap-2.5', 'h-11 px-4')}>
              <span className="inline-flex size-5 items-center justify-center rounded-xs bg-sunken text-11 font-semibold text-fg-3 shadow-[inset_0_0_0_1px_var(--c-line-soft)]">{app[0]}</span>
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

        <Section title={t('settings.privacy.password')}>
          <p className={cx('text-13 leading-[20px] text-fg-2', pad)}>{t('settings.privacy.passwordDesc')}</p>
        </Section>

        <Section title={t('settings.privacy.storage')}>
          {(
            [
              ['storeKey', 'storeKeyVal'],
              ['storeText', 'storeTextVal'],
              ['storeLogs', 'storeLogsVal'],
            ] as const
          ).map(([k, v]) => (
            <div key={k} className={cx('flex items-center justify-between gap-6 text-13', pad)}>
              <span className="text-fg-2">{t(`settings.privacy.${k}`)}</span>
              <span className="text-right text-fg">{t(`settings.privacy.${v}`)}</span>
            </div>
          ))}
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
  const [copied, setCopied] = useState(false)
  const pad = 'px-4 py-3'
  const rows: [string, React.ReactNode][] = [
    [t('settings.about.version'), '0.1.0 (prototype)'],
    [
      t('settings.about.engine'),
      <span className="inline-flex items-center gap-1.5">
        <span className="size-1.5 rounded-full bg-success" />
        {t('settings.about.running')}
      </span>,
    ],
    [
      t('settings.about.ime'),
      <span className="inline-flex items-center gap-1.5">
        <span className="size-1.5 rounded-full bg-success" />
        {t('settings.about.imeVal')} 1.2 — {t('settings.about.connected')}
      </span>,
    ],
    // Required attribution (CC BY-SA 4.0) for the local dictionary.
    [t('settings.about.dict'), 'CC-CEDICT · CC BY-SA 4.0'],
  ]
  return (
    <>
      <div className="mb-6 flex items-center gap-3.5">
        <AppMark size={48} />
        <div>
          <h2 className={cx('font-semibold tracking-[-0.01em] text-fg', 'text-22')}>{t('app.name')}</h2>
          <p className="text-13 text-fg-3">{t('settings.about.license')}</p>
        </div>
      </div>
      <div className="flex flex-col gap-7">
        <Section>
          {rows.map(([k, v]) => (
            <div key={k} className={cx('flex items-center justify-between gap-6 text-13', pad)}>
              <span className="text-fg-2">{k}</span>
              <span className="text-fg tnum">{v}</span>
            </div>
          ))}
          <div className={pad}>
            <Button onClick={() => setCopied(true)}>
              {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
              {copied ? t('settings.about.copied') : t('settings.about.copyDiag')}
            </Button>
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

/* =========================================================== Overview (direction B) */

export function OverviewPage({ go }: { go: (p: 'general' | 'translation') => void }) {
  const { t } = useTranslation()
  const [d, set] = useDraft()
  const paused = useReview((r) => r.paused)
  const setp = useReview((r) => r.setp)
  const lang = TARGETS.find((x) => x.id === d.target)!.native
  const [keys, setKeys] = useState<Partial<Record<ProviderId, boolean>>>({})
  useEffect(() => {
    bridge?.keys().then(setKeys)
  }, [])
  const serviceReady = d.localOnly || !!keys[d.provider] || !!d.apiKey || serviceOf(d).auth === 'none'
  return (
    <>
      <PageHeader title={t('settings.overview.title')} desc={t('settings.overview.desc')} />
      <div className="flex flex-col gap-5">
        <Section>
          <div className="flex items-center gap-3 px-4 py-3.5">
            <span className={cx('relative inline-flex size-8 items-center justify-center rounded-lg', paused ? 'bg-sunken text-fg-3' : 'bg-accent-soft text-accent-text')}>
              {paused ? <Pause className="size-4" /> : <Check className="size-4" strokeWidth={2.25} />}
            </span>
            <div className="flex-1">
              <div className="text-14 font-semibold text-fg">{paused ? t('settings.overview.statusPaused') : t('settings.overview.statusOk', { lang })}</div>
              <div className="text-12 text-fg-3">
                {t('settings.about.imeVal')} · {t('settings.about.connected')}
              </div>
            </div>
            <label className="flex items-center gap-2.5 text-13 text-fg-2">
              {t('settings.overview.active')}
              {/* On (lit) while translating, off (dimmed) when paused — the switch states what is happening. */}
              <Switch label={t('settings.overview.active')} checked={!paused} onCheckedChange={(v) => setp({ paused: !v })} />
            </label>
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

        {/* The only real setup: a translation service (optional). Shown until one is connected or Local only is on. */}
        {!serviceReady && (
          <Section>
            <div className="flex items-center gap-3 px-4 py-3.5">
              <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-lg bg-sunken text-fg-3">
                <Cloud className="size-4" />
              </span>
              <div className="flex-1">
                <div className="text-14 font-semibold text-fg">{t('settings.overview.serviceTitle')}</div>
                <div className="text-12 text-fg-3">{t('settings.overview.serviceDesc')}</div>
              </div>
              <Button onClick={() => go('translation')}>
                {t('settings.overview.serviceSetup')}
                <ArrowRight className="size-3.5" />
              </Button>
            </div>
          </Section>
        )}

        <Section title={t('settings.overview.reach')} desc={t('settings.overview.reachDesc')}>
          <ReachRow icon={<Kbd>.exe</Kbd>} label={t('settings.overview.reachRelaunch')} />
          <ReachRow icon={<Shortcut keys={d.shortcuts.settings} />} label={t('settings.general.sc.settings')} />
          <ReachRow icon={<Shortcut keys={d.shortcuts.pause} />} label={t('settings.general.sc.pause')} />
          <ReachRow icon={<Shortcut keys={d.shortcuts.toggleBar} />} label={t('settings.general.sc.toggleBar')} />
          <ReachRow icon={<Power className="size-3.5 text-fg-3" />} label={t('settings.overview.reachQuit')} />
        </Section>
      </div>
    </>
  )
}

function ReachRow({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <div className="flex items-center gap-3 px-4 py-2.5 text-13 text-fg-2">
      <span className="flex-1">{label}</span>
      {icon}
    </div>
  )
}
