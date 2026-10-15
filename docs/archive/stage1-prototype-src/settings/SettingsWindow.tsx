import { useEffect, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Gauge, Info, Languages, Minus, Palette, Settings2, ShieldCheck, X, Pause, Play } from 'lucide-react'
import { useReview, useSettings, type Page } from '../store'
import { Button, cx } from '../ui/primitives'
import { useScope } from '../ui/scope'
import { AboutPage, AppGlyph, AppearancePage, GeneralPage, OverviewPage, PrivacyPage, TranslationPage } from './pages'

const NAV: { id: Page; icon: typeof Gauge }[] = [
  { id: 'overview', icon: Gauge },
  { id: 'general', icon: Settings2 },
  { id: 'translation', icon: Languages },
  { id: 'appearance', icon: Palette },
  { id: 'privacy', icon: ShieldCheck },
  { id: 'about', icon: Info },
]

/** Frameless window chrome with Windows caption buttons. */
function WindowFrame({ title, children, onClose, width, height }: { title: string; children: ReactNode; onClose: () => void; width: number; height: number }) {
  const { dir } = useScope()
  return (
    <div
      role="dialog"
      aria-label={title}
      className={cx('flex flex-col overflow-hidden bg-app text-fg shadow-window', dir === 'a' ? 'rounded-lg' : 'rounded-xl')}
      style={{ width, height }}
    >
      <div className="flex h-8 shrink-0 select-none items-center">
        <div className="flex flex-1 items-center gap-2 pl-3 text-12 text-fg-3">
          <AppGlyph size={14} />
          {title}
        </div>
        <button type="button" tabIndex={-1} aria-label="Minimize" className="inline-flex h-8 w-11 items-center justify-center text-fg-3 hover:bg-hover">
          <Minus className="size-3.5" strokeWidth={1.5} />
        </button>
        <button type="button" aria-label="Close" onClick={onClose} className="inline-flex h-8 w-11 items-center justify-center text-fg-3 hover:bg-[oklch(0.58_0.21_27)] hover:text-white">
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

/* ================================================================ A */

export function SettingsA({ onClose, onQuit }: { onClose: () => void; onQuit: () => void }) {
  const { t } = useTranslation()
  const page0 = useReview((r) => r.page)
  const page = page0 === 'overview' ? 'general' : page0
  const setp = useReview((r) => r.setp)
  const paused = useReview((r) => r.paused)
  const pauseKey = useSettings((s) => s.saved.shortcuts.pause)
  const { count, save, cancel, justSaved } = useSave()
  const go = (p: Page) => setp({ page: p })

  return (
    <WindowFrame title={t('settings.title')} onClose={onClose} width={800} height={580}>
      <nav className="flex w-[200px] shrink-0 flex-col bg-side px-2 pb-2 pt-1" aria-label={t('settings.title')}>
        <div className="flex h-9 items-center gap-2 px-2 pb-1 text-13 font-semibold text-fg">
          <AppGlyph size={18} />
          {t('app.name')}
        </div>
        <ul className="flex flex-col gap-px">
          {NAV.filter((n) => n.id !== 'overview').map(({ id, icon: Icon }) => (
            <li key={id}>
              <button
                type="button"
                onClick={() => go(id)}
                aria-current={page === id ? 'page' : undefined}
                className={cx(
                  'focus-ring flex h-7 w-full items-center gap-2 rounded-sm px-2 text-13 transition-colors duration-[var(--dur-1)]',
                  page === id ? 'bg-select font-medium text-fg' : 'text-fg-2 hover:bg-hover hover:text-fg',
                )}
              >
                <Icon className={cx('size-3.5', page === id ? 'text-fg-2' : 'text-fg-3')} strokeWidth={2} />
                {t(`settings.nav.${id}`)}
              </button>
            </li>
          ))}
        </ul>
        <div className="mt-auto flex flex-col gap-1 border-t border-line-soft pt-2">
          <button
            type="button"
            onClick={() => setp({ paused: !paused })}
            className="focus-ring flex h-7 items-center gap-2 rounded-sm px-2 text-13 text-fg-2 hover:bg-hover hover:text-fg"
          >
            {paused ? <Play className="size-3.5 text-fg-3" strokeWidth={2} /> : <Pause className="size-3.5 text-fg-3" strokeWidth={2} />}
            <span className="min-w-0 flex-1 truncate text-left">{t(paused ? 'bar.menu.resume' : 'bar.menu.pause')}</span>
            <span className="shrink-0 text-11 text-fg-4 tnum">{pauseKey}</span>
          </button>
          <div className="flex h-6 items-center gap-2 px-2 text-12 text-fg-3">
            <span className={cx('size-1.5 rounded-full', paused ? 'bg-fg-4' : 'bg-success')} />
            {paused ? t('bar.status.paused') : t('bar.status.ready')}
          </div>
        </div>
      </nav>

      <div className="relative flex min-w-0 flex-1 flex-col bg-app">
        <div className="scroll-quiet min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto max-w-[600px] px-8 pb-24 pt-6">
            <PageBody page={page} go={go} onQuit={onQuit} />
          </div>
        </div>
        {(count > 0 || justSaved) && (
          <div className="anim-pop pointer-events-none absolute inset-x-0 bottom-4 flex justify-center">
            <div className="pointer-events-auto flex h-10 items-center gap-3 rounded-lg bg-raised pl-3.5 pr-1.5 shadow-pop">
              <span className="text-13 text-fg-2">
                {count > 0 ? t('settings.footer.unsavedCount', { count }) : t('settings.footer.allSaved')}
              </span>
              {count > 0 && (
                <>
                  <Button size="md" variant="ghost" onClick={cancel}>
                    {t('settings.footer.cancel')}
                  </Button>
                  <Button size="md" variant="primary" onClick={save}>
                    {t('settings.footer.save')}
                  </Button>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </WindowFrame>
  )
}

/* ================================================================ B */

export function SettingsB({ onClose, onQuit }: { onClose: () => void; onQuit: () => void }) {
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
          <AppGlyph size={28} />
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
        <button
          type="button"
          onClick={() => setp({ paused: !paused })}
          className="focus-ring mt-auto flex h-8 items-center gap-2.5 rounded-md px-2.5 text-13 font-medium text-fg-2 hover:bg-hover hover:text-fg"
        >
          {paused ? <Play className="size-4 text-fg-3" strokeWidth={1.75} /> : <Pause className="size-4 text-fg-3" strokeWidth={1.75} />}
          {paused ? t('bar.menu.resume') : t('bar.menu.pause')}
        </button>
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
