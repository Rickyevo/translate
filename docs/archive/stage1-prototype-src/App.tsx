import { useEffect } from 'react'
import * as RTooltip from '@radix-ui/react-tooltip'
import { Moon, Sun } from 'lucide-react'
import i18n, { UI_LANGS, UI_LANG_NATIVE, resolveLang, type UiLang } from './i18n'
import { TARGETS, type Target } from './data/scenarios'
import { effectiveSettings, syncUrl, useReview, useSettings, type Dir, type View } from './store'
import { Scope } from './ui/scope'
import { Segmented, Select, cx } from './ui/primitives'
import { DesktopDemo } from './views/DesktopDemo'
import { StatesBoard } from './views/StatesBoard'
import { Showcase } from './views/Showcase'
import { SettingsA, SettingsB } from './settings/SettingsWindow'

const VIEWS: { id: View; label: string }[] = [
  { id: 'desktop', label: 'Desktop' },
  { id: 'states', label: 'Bar states' },
  { id: 'settings', label: 'Settings' },
  { id: 'components', label: 'Components' },
]

export default function App() {
  const r = useReview()
  const st = useSettings()
  const eff = effectiveSettings(st)
  const lang = resolveLang(eff.uiLang)

  // Interface language previews live from the draft, like other live settings.
  useEffect(() => {
    if (i18n.language !== lang) i18n.changeLanguage(lang)
    document.documentElement.lang = lang
  }, [lang])
  useEffect(() => {
    syncUrl()
  }, [r.dir, r.theme, r.view, r.scenario, r.page, st.saved.uiLang, st.saved.target])

  const setLang = (l: UiLang | 'system') =>
    useSettings.setState((s) => ({ saved: { ...s.saved, uiLang: l }, draft: { ...s.draft, uiLang: l } }))
  const setTarget = (t: Target) => useSettings.setState((s) => ({ saved: { ...s.saved, target: t }, draft: { ...s.draft, target: t } }))

  return (
    <RTooltip.Provider>
      <Scope dir={r.dir} theme={r.theme} lang={lang} className="flex h-full flex-col bg-app text-fg">
        {/* Review chrome — not part of the product */}
        <header className="flex h-11 shrink-0 items-center gap-3 border-b border-line-soft px-3">
          <span className="text-13 font-semibold text-fg">Stage 1 prototypes</span>
          <Segmented<Dir>
            label="Direction"
            value={r.dir}
            onValueChange={(d) => r.setp({ dir: d })}
            options={[
              { value: 'a', label: 'A · Ribbon' },
              { value: 'b', label: 'B · Panel' },
            ]}
          />
          <nav className="flex items-center gap-0.5">
            {VIEWS.map((v) => (
              <button
                key={v.id}
                type="button"
                onClick={() => r.setp({ view: v.id })}
                className={cx(
                  'focus-ring h-7 rounded-sm px-2.5 text-13 transition-colors',
                  r.view === v.id ? 'bg-select font-medium text-fg' : 'text-fg-3 hover:bg-hover hover:text-fg',
                )}
              >
                {v.label}
              </button>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <Select<UiLang | 'system'>
              label="Interface language"
              className="w-[118px]"
              value={st.saved.uiLang}
              onValueChange={setLang}
              options={UI_LANGS.map((l) => ({ value: l, label: UI_LANG_NATIVE[l], lang: l }))}
            />
            <Select<Target>
              label="Target language"
              className="w-[118px]"
              value={st.saved.target}
              onValueChange={setTarget}
              options={TARGETS.slice(0, 3).map((x) => ({ value: x.id, label: '→ ' + x.native, lang: x.id }))}
            />
            <Segmented
              label="Theme"
              value={r.theme}
              onValueChange={(th) => r.setp({ theme: th })}
              options={[
                { value: 'light', label: '', icon: <Sun className="size-3.5" aria-label="Light" /> },
                { value: 'dark', label: '', icon: <Moon className="size-3.5" aria-label="Dark" /> },
              ]}
            />
          </div>
        </header>

        {r.view === 'desktop' && <DesktopDemo />}
        {r.view === 'states' && <StatesBoard dir={r.dir} />}
        {r.view === 'components' && <Showcase />}
        {r.view === 'settings' && (
          <div
            className="flex min-h-0 flex-1 items-center justify-center overflow-auto p-6"
            style={{ background: r.theme === 'light' ? 'oklch(0.9 0.01 250)' : 'oklch(0.13 0.005 250)' }}
          >
            {r.dir === 'a' ? <SettingsA onClose={() => {}} onQuit={() => {}} /> : <SettingsB onClose={() => {}} onQuit={() => {}} />}
          </div>
        )}
      </Scope>
    </RTooltip.Provider>
  )
}
