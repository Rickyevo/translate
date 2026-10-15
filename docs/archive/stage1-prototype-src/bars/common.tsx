import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { CircleAlert, CloudOff, HardDrive, KeyRound, Pause, MoreHorizontal, Settings2, EyeOff, Power, Play, RotateCw } from 'lucide-react'
import type { Banner, CandidateList, Item, Target } from '../data/scenarios'
import type { Settings } from '../store'
import { Kbd, Menu, MenuContent, MenuItem, MenuSeparator, MenuTrigger, cx } from '../ui/primitives'

export interface BarActions {
  paused: boolean
  onInsert?: (n: number) => void
  onRetry?: (n: number) => void
  onPause?: () => void
  onHide?: () => void
  onSettings?: () => void
  onQuit?: () => void
}

export interface BarProps extends BarActions {
  list: CandidateList
  s: Settings
  /** Show the original candidate: resolved per direction from settings. */
  altHeld?: boolean
  /** Forced states for the static state board. */
  forceHover?: number
  forcePeek?: number
  flash?: number
  nudge?: number
  /** Where the bar sits relative to the IME window — peeks open away from it. */
  placement?: 'below' | 'above'
  /** Horizontal room: peek flips side near the right screen edge. */
  edge?: 'none' | 'right'
  menuOpen?: boolean
}

export function langAttr(t: Target) {
  return t === 'en' ? 'en' : t
}

/** Short code for the language pair indicator. */
export const TARGET_CODE: Record<Target, string> = { en: 'EN', ja: 'JA', ko: 'KO', fr: 'FR', de: 'DE', es: 'ES', ru: 'RU' }

export function bannerMeta(b: Banner) {
  switch (b) {
    case 'offline':
      return { icon: CloudOff, tone: 'warning' as const, short: 'bar.status.offline', long: 'bar.status.offlineLong' }
    case 'localOnly':
      return { icon: HardDrive, tone: 'neutral' as const, short: 'bar.status.localOnly', long: 'bar.status.localOnlyLong' }
    case 'failed':
      return { icon: CircleAlert, tone: 'warning' as const, short: 'bar.status.failed', long: 'bar.status.failedLong' }
    case 'auth':
      return { icon: KeyRound, tone: 'danger' as const, short: 'bar.status.auth', long: 'bar.status.authLong' }
    case 'paused':
      return { icon: Pause, tone: 'neutral' as const, short: 'bar.status.paused', long: 'bar.status.pausedLong' }
    default:
      return null
  }
}

export const toneText = { warning: 'text-warning', danger: 'text-danger', neutral: 'text-fg-3' }

/** Delayed hover → peek, so sweeping the mouse across the bar doesn't flash popovers. */
export function usePeek(force?: number) {
  const [peek, setPeek] = useState<number | null>(null)
  const timer = useRef<number | undefined>(undefined)
  const enter = (n: number) => {
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setPeek(n), peek === null ? 380 : 60)
  }
  const leave = () => {
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setPeek(null), 120)
  }
  useEffect(() => () => window.clearTimeout(timer.current), [])
  return { peek: force ?? peek, enter, leave, setPeek }
}

/** Content of the detail popover — identical in both directions. */
export function PeekBody({ item, s, showOriginal }: { item: Item; s: Settings; showOriginal: boolean }) {
  const { t } = useTranslation()
  const key = `Alt+${item.n}`
  if (item.state === 'failed' || item.state === 'noEntry') {
    return (
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center gap-1.5 text-13 font-medium text-fg">
          {item.state === 'failed' ? <CircleAlert className="size-3.5 text-danger" strokeWidth={2} /> : null}
          {item.state === 'failed' ? t('bar.failed') : t('bar.noEntry')}
          <span className="font-normal text-fg-3" lang="zh-CN">
            {item.text}
          </span>
        </div>
        <p className="text-12 leading-[18px] text-fg-2">{t(`bar.reason.${item.reason ?? 'network'}`)}</p>
        {item.state === 'failed' && (
          <div className="flex items-center gap-1.5 pt-0.5 text-12 text-fg-3">
            <RotateCw className="size-3" strokeWidth={2} /> {t('bar.clickHint', { key })}
          </div>
        )}
      </div>
    )
  }
  if (item.state === 'loading') {
    return (
      <div className="flex flex-col gap-1">
        <div className="text-13 text-fg-2">{t('bar.loading')}…</div>
        <div className="text-12 text-fg-3" lang="zh-CN">
          {item.text}
        </div>
      </div>
    )
  }
  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-fg" style={{ fontSize: s.textSize + 1, lineHeight: 1.45 }} lang={langAttr(s.target)}>
        {item.translation}
      </p>
      <div className="flex items-center gap-2 text-12 text-fg-3">
        {showOriginal && (
          <span className="text-fg-2" lang="zh-CN">
            {item.text}
          </span>
        )}
        {item.source && <span>{t(`bar.source.${item.source}`)}</span>}
        <span className="ml-auto inline-flex items-center gap-1 whitespace-nowrap">
          <Kbd>Alt</Kbd>
          <Kbd>{item.n}</Kbd>
        </span>
      </div>
    </div>
  )
}

/** The bar's ⋯ menu: the tray-free home for pause / settings / quit. */
export function BarMenu({ paused, onPause, onHide, onSettings, onQuit, s, trigger, open }: BarActions & { s: Settings; trigger: ReactNode; open?: boolean }) {
  const { t } = useTranslation()
  return (
    <Menu modal={false} open={open}>
      <MenuTrigger asChild>{trigger}</MenuTrigger>
      <MenuContent side="bottom" align="end">
        <MenuItem icon={paused ? <Play className="size-3.5" /> : <Pause className="size-3.5" />} shortcut={s.shortcuts.pause} onSelect={onPause}>
          {paused ? t('bar.menu.resume') : t('bar.menu.pause')}
        </MenuItem>
        <MenuItem icon={<EyeOff className="size-3.5" />} shortcut={s.shortcuts.toggleBar} onSelect={onHide}>
          {t('bar.menu.hide')}
        </MenuItem>
        <MenuItem icon={<Settings2 className="size-3.5" />} shortcut={s.shortcuts.settings} onSelect={onSettings}>
          {t('bar.menu.settings')}
        </MenuItem>
        <MenuSeparator />
        <MenuItem icon={<Power className="size-3.5" />} onSelect={onQuit}>
          {t('bar.menu.quit')}
        </MenuItem>
      </MenuContent>
    </Menu>
  )
}

export function MoreButton({ label, className, ...p }: { label: string; className?: string } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      tabIndex={-1}
      onMouseDown={(e) => e.preventDefault() /* never take focus from the input field */}
      className={cx(
        'inline-flex shrink-0 items-center justify-center rounded-sm text-fg-3 transition-colors duration-[var(--dur-1)] hover:bg-hover hover:text-fg-2 data-[state=open]:bg-press data-[state=open]:text-fg',
        className,
      )}
      {...p}
    >
      <MoreHorizontal className="size-3.5" strokeWidth={2} />
    </button>
  )
}

export function insertable(item: Item) {
  return item.state === 'done' && !!item.translation
}
