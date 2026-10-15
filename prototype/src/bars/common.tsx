import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { BookOpen, CircleAlert, CloudOff, FlaskConical, HardDrive, KeyRound, Pause, MoreHorizontal, Settings2, EyeOff, Power, Play } from 'lucide-react'
import type { Banner, CandidateList, Item, Target } from '../data/scenarios'
import type { Settings } from '../store'
import { Menu, MenuContent, MenuItem, MenuSeparator, MenuTrigger, cx } from '../ui/primitives'

export interface BarActions {
  paused: boolean
  onInsert?: (n: number) => void
  onCopy?: (n: number) => void
  onRetry?: (n: number) => void
  onTarget?: (t: Target) => void
  onPause?: () => void
  onHide?: () => void
  onSettings?: () => void
  onQuit?: () => void
}

export interface BarProps extends BarActions {
  list: CandidateList
  s: Settings
  altHeld?: boolean
  /** Forced states for the static state board. */
  forceHover?: number
  /** Row currently previewed by hover (kept highlighted). */
  hoverRow?: number
  onHoverRow?: (n: number | undefined, eligible?: boolean) => void
  onLeadTruncated?: (truncated: boolean) => void
  /** Candidate 1 is cut off but there is no room to show its full text. */
  leadMore?: boolean
  flash?: number
  nudge?: number
  /** Where the bar sits relative to the IME window — peeks open away from it. */
  placement?: 'below' | 'above'
  /** Horizontal room: peek flips side near the right screen edge. */
  edge?: 'none' | 'right'
  menuOpen?: boolean
  /** Changes when a new composition starts; width may only grow within one. */
  compositionKey?: unknown
  /** Row whose context menu is open (kept highlighted). */
  ctxOpen?: number
  onCtx?: (n: number | undefined) => void
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
    case 'noService': // no key / model yet: cache and dictionary still work
      return { icon: BookOpen, tone: 'neutral' as const, short: 'bar.status.noService', long: 'bar.status.noServiceLong' }
    case 'simulated': // stage 4: real candidates, placeholder translations until a provider is connected
      return { icon: FlaskConical, tone: 'warning' as const, short: 'bar.status.simulated', long: 'bar.status.simulatedLong' }
    default:
      return null
  }
}

export const toneText = { warning: 'text-warning', danger: 'text-danger', neutral: 'text-fg-3' }

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
