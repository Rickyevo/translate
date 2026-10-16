/* Settings renderer — created on demand, destroyed on close (its renderer process exits).
 * Reuses the approved settings UI; this file only wires the shared store to the main process. */
import { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import * as RTooltip from '@radix-ui/react-tooltip'
import i18n, { resolveLang } from '../../../prototype/src/i18n'
import { SettingsWindow } from '../../../prototype/src/settings/SettingsWindow'
import { effectiveSettings, useReview, useSettings, type Page } from '../../../prototype/src/store'
import { Scope } from '../../../prototype/src/ui/scope'
import { setBridge, type TestResult } from '../../../prototype/src/settings/bridge'
import type { ThemeName, TranslateApi } from '../shared/types'
import './app.css'

const api = (window as unknown as { translate: TranslateApi }).translate
const page = new URLSearchParams(location.search).get('page') as Page | null

// Real service calls, key presence, cache and logs for the shared settings pages.
setBridge({
  test: async (svc, key) => {
    const r = await api.svcTest(svc, key)
    return (r.ok ? { ok: true, ms: r.ms ?? 0 } : { ok: false, error: r.error ?? 'http', status: r.status, detail: r.detail }) as TestResult
  },
  models: (svc, key) => api.svcModels(svc, key),
  keys: () => api.svcKeys(),
  cacheStats: () => api.cacheStats(),
  clearCache: () => api.cacheClear(),
  openLogs: () => api.openLogs(),
  status: () => api.statusGet(),
})

function SettingsApp() {
  const [ready, setReady] = useState(false)
  const [osTheme, setOsTheme] = useState<ThemeName>('light')
  const st = useSettings()
  const eff = effectiveSettings(st)

  useEffect(() => {
    api.getSettings().then(({ saved, theme, paused, version }) => {
      useSettings.setState({ saved, draft: saved })
      useReview.setState({ paused, version, page: page ?? 'overview' })
      setOsTheme(theme)
      setReady(true)
    })
    api.onTheme(setOsTheme)
    // Keep the pause switch and sidebar in step when pausing happens outside this window. Setting the same value
    // back is a no-op, so this can't loop through the subscription below.
    api.onPaused((p) => useReview.getState().paused !== p && useReview.setState({ paused: p }))
    // Store → main: save, live draft, pause.
    const unSettings = useSettings.subscribe((s, prev) => {
      if (s.saved !== prev.saved)
        void api.saveSettings(s.saved).then(() => {
          // The key now lives in Windows Credential Manager; drop it from this window's memory too.
          if (s.saved.apiKey) useSettings.setState((x) => ({ saved: { ...x.saved, apiKey: '' }, draft: { ...x.draft, apiKey: '' } }))
        })
      else if (s.draft !== prev.draft) api.draftSettings(s.draft)
    })
    const unReview = useReview.subscribe((r, prev) => r.paused !== prev.paused && api.setPaused(r.paused))
    return () => (unSettings(), unReview())
  }, [])

  const lang = resolveLang(eff.uiLang)
  useEffect(() => {
    i18n.changeLanguage(lang)
    document.documentElement.lang = lang
  }, [lang])

  const theme: ThemeName = eff.theme === 'system' ? osTheme : eff.theme
  if (!ready) return null
  return (
    <RTooltip.Provider>
      <Scope theme={theme} lang={lang} className="h-full">
        <SettingsWindow onClose={() => api.windowAction('close')} onQuit={() => api.quit()} />
      </Scope>
    </RTooltip.Provider>
  )
}

createRoot(document.getElementById('root')!).render(<SettingsApp />)
