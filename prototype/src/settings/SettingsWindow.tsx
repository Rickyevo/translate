import { useEffect, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Gauge, Info, Languages, Minus, Palette, Settings2, ShieldCheck, X } from 'lucide-react'
import { useReview, useSettings, type Page } from '../store'
import { Button, cx } from '../ui/primitives'
import { AppMark } from '../icons/AppMark'
import { AboutPage, AppearancePage, GeneralPage, OverviewPage, PrivacyPage, TranslationPage } from './pages'

const NAV: { id: Page; icon: typeof Gauge }[] = [
  { id: 'overview', icon: Gauge },
  { id: 'general', icon: Settings2 },
  { id: 'translation', icon: Languages },
  { id: 'appearance', icon: Palette },
  { id: 'privacy', icon: ShieldCheck },
  { id: 'about', icon: Info },
]

/** Frameless window chrome with Windows caption buttons. In the app the OS window is the frame: fill it, make the
 *  title bar draggable. */
const host = typeof window !== 'undefined' ? (window as unknown as { translate?: { windowAction(a: 'close' | 'minimize'): void } }).translate : undefined

function WindowFrame({ title, children, onClose, width, height }: { title: string; children: ReactNode; onClose: () => void; width: number; height: number }) {
  return (
    <div
      role="dialog"
      aria-label={title}
      className={cx('flex flex-col overflow-hidden bg-app text-fg', !host && 'rounded-xl shadow-window')}
      style={host ? { width: '100vw', height: '100vh' } : { width, height }}
    >
      <div className="flex h-8 shrink-0 select-none items-center [-webkit-app-region:drag]">
        <div className="flex flex-1 items-center gap-2 pl-3 text-12 text-fg-3">
          <AppMark size={16} />
          {title}
        </div>
        <button type="button" tabIndex={-1} aria-label="Minimize" onClick={() => host?.windowAction('minimize')} className="inline-flex h-8 w-11 items-center justify-center text-fg-3 [-webkit-app-region:no-drag] hover:bg-hover">
          <Minus className="size-3.5" strokeWidth={1.5} />
        </button>
        <button type="button" aria-label="Close" onClick={onClose} className="inline-flex h-8 w-11 items-center justify-center text-fg-3 [-webkit-app-region:no-drag] hover:bg-[oklch(0.58_0.21_27)] hover:text-white">
          <X className="size-3.5" strokeWidth={1.5} />
        </button>
      </div>
      <div className="flex min-h-0 flex-1">{children}</div>
    </div>
  )
}

function useSave() {
  const saved = useSettings((s) => s.saved)
  const draft = useSettings((s) => s.draft)
  const dirty = (Object.keys(draft) as (keyof typeof draft)[]).filter((k) => JSON.stringify(draft[k]) !== JSON.stringify(saved[k]))
  const save = useSettings((s) => s.save)
  const cancel = useSettings((s) => s.cancel)
  const [justSaved, setJustSaved] = useState(false)
  useEffect(() => {
    if (!justSaved) return
    const id = window.setTimeout(() => setJustSaved(false), 1600)
    return () => window.clearTimeout(id)
  }, [justSaved])
  return {
    count: dirty.length,
    save: () => (save(), setJustSaved(true)),
    cancel,
    justSaved,
  }
}

function PageBody({ page, go, onQuit }: { page: Page; go: (p: Page) => void; onQuit: () => void }) {
  switch (page) {
    case 'overview':
      return <OverviewPage go={go} />
    case 'general':
      return <GeneralPage />
    case 'translation':
      return <TranslationPage />
    case 'appearance':
      return <AppearancePage />
    case 'privacy':
      return <PrivacyPage />
    case 'about':
      return <AboutPage onQuit={onQuit} />
  }
}

export function SettingsWindow({ onClose, onQuit }: { onClose: () => void; onQuit: () => void }) {
  const { t } = useTranslation()
  const page = useReview((r) => r.page)
  const setp = useReview((r) => r.setp)
  const paused = useReview((r) => r.paused)
  const { count, save, cancel, justSaved } = useSave()
  const go = (p: Page) => setp({ page: p })

  return (
    <WindowFrame title={t('settings.title')} onClose={onClose} width={860} height={620}>
      <nav className="flex w-[216px] shrink-0 flex-col gap-4 px-3 pb-3 pt-2" aria-label={t('settings.title')}>
        <div className="flex items-center gap-2.5 px-1.5">
          <AppMark size={28} />
          <div className="min-w-0">
            <div className="text-14 font-semibold text-fg">{t('app.name')}</div>
            <div className="flex items-center gap-1.5 text-12 text-fg-3">
              <span className={cx('size-1.5 rounded-full', paused ? 'bg-fg-4' : 'bg-success')} />
              {paused ? t('bar.status.paused') : t('bar.status.ready')}
            </div>
          </div>
        </div>
        <ul className="flex flex-col gap-0.5">
          {NAV.map(({ id, icon: Icon }) => (
            <li key={id}>
              <button
                type="button"
                onClick={() => go(id)}
                aria-current={page === id ? 'page' : undefined}
                className={cx(
                  'focus-ring flex h-8 w-full items-center gap-2.5 rounded-md px-2.5 text-13 font-medium transition-colors duration-[var(--dur-1)]',
                  page === id ? 'bg-surface text-fg shadow-[var(--sh-control),0_0_0_1px_var(--c-line-soft)]' : 'text-fg-2 hover:bg-hover hover:text-fg',
                )}
              >
                <Icon className={cx('size-4', page === id ? 'text-accent-text' : 'text-fg-3')} strokeWidth={1.75} />
                {t(`settings.nav.${id}`)}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="scroll-quiet min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto max-w-[600px] px-7 pb-8 pt-5">
            <PageBody page={page} go={go} onQuit={onQuit} />
          </div>
        </div>
        <footer className="flex h-[52px] shrink-0 items-center gap-2 border-t border-line-soft px-5">
          <span className={cx('flex-1 text-13', count > 0 ? 'text-fg-2' : 'text-fg-3')}>
            {count > 0 ? (
              <span className="inline-flex items-center gap-2">
                <span className="size-1.5 rounded-full bg-warning" />
                {t('settings.footer.unsavedCount', { count })}
              </span>
            ) : justSaved ? (
              t('settings.footer.saved')
            ) : (
              t('settings.footer.allSaved')
            )}
          </span>
          <Button onClick={cancel} disabled={count === 0}>
            {t('settings.footer.cancel')}
          </Button>
          <Button variant="primary" onClick={save} disabled={count === 0}>
            {t('settings.footer.save')}
          </Button>
        </footer>
      </div>
    </WindowFrame>
  )
}
