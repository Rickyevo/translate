import { forwardRef, type CSSProperties } from 'react'
import { useTranslation } from 'react-i18next'
import { CircleAlert, Copy, CornerDownLeft, RotateCw, X } from 'lucide-react'
import type { Item } from '../data/scenarios'
import type { Settings } from '../store'
import { cx } from '../ui/primitives'
import { insertable, langAttr } from './common'

export interface LeadPreviewProps {
  item: Item
  s: Settings
  /** Previous candidate #1 text, shown dimmed while the new #1 is still translating. */
  stale?: string
  /** Card height; content scrolls inside when the text needs more. Omit to measure natural height. */
  height?: number
  overlay?: boolean
  scrollable?: boolean
  onInsert?: (n: number) => void
  onCopy?: (n: number) => void
  onRetry?: (n: number) => void
  onCollapse?: () => void
  style?: CSSProperties
  className?: string
}

/** Max visible lines before the text scrolls. */
export const LEAD_MAX_LINES = 6
export const leadLineHeight = (fs: number) => Math.round((fs + 1) * 1.45)

/**
 * Full text of one candidate — #1 by default, or the row being hovered/stepped to.
 * Passive: the body never inserts. Every mousedown is swallowed so the app keeps focus.
 */
export const LeadPreview = forwardRef<HTMLDivElement, LeadPreviewProps>(function LeadPreview(p, scrollRef) {
  const { t } = useTranslation()
  const { item, s } = p
  const fs = s.textSize + 1
  const lh = leadLineHeight(s.textSize)
  const measuring = p.height === undefined
  const ok = insertable(item)
  const failed = item.state === 'failed' || item.state === 'noEntry'
  const loading = item.state === 'loading'

  return (
    <div
      role="region"
      aria-label={t('bar.preview.label', { n: item.n })}
      aria-live="polite"
      onMouseDown={(e) => e.preventDefault() /* never take focus from the app */}
      className={cx('flex flex-col rounded-xl shadow-bar backdrop-blur-md', p.overlay && 'shadow-pop', p.className)}
      style={{
        background: `color-mix(in oklch, var(--bar-bg) ${Math.round(Math.max(s.opacity, p.overlay ? 1 : 0) * 100)}%, transparent)`,
        height: p.height,
        ...p.style,
      }}
    >
      <div className="flex min-h-0 flex-1 items-start gap-2 pl-3 pr-1.5 pt-2.5">
        <span
          className={cx(
            'tnum mt-[2px] inline-flex size-4 shrink-0 items-center justify-center rounded-xs text-11 font-semibold',
            failed ? 'bg-danger-soft text-danger-text' : 'bg-accent-soft text-accent-text',
          )}
        >
          {item.n}
        </span>
        <div
          ref={scrollRef}
          className={cx('scroll-quiet min-h-0 flex-1 pr-1', !measuring && 'overflow-y-auto', !measuring && p.scrollable && 'lead-fade')}
          style={{ maxHeight: measuring ? LEAD_MAX_LINES * lh : undefined }}
        >
          {failed ? (
            <div className="flex flex-col gap-1 pb-1">
              <span className="flex items-center gap-1.5 text-13 font-medium text-fg">
                {item.state === 'failed' && <CircleAlert className="size-3.5 text-danger" strokeWidth={2} />}
                {item.state === 'failed' ? t('bar.failed') : t('bar.noEntry')}
              </span>
              <span className="text-12 leading-[18px] text-fg-2">{t(`bar.reason.${item.reason ?? 'network'}`)}</span>
            </div>
          ) : loading && !p.stale ? (
            <div className="flex flex-col gap-2 py-1" aria-label={t('bar.loading')}>
              <span className="skeleton block h-2 w-[92%] rounded-full" />
              <span className="skeleton block h-2 w-[64%] rounded-full" />
            </div>
          ) : (
            <p
              lang={langAttr(s.target)}
              className={cx('pb-1 text-fg transition-opacity duration-[var(--dur-2)]', loading && 'opacity-45')}
              style={{ fontSize: fs, lineHeight: `${lh}px`, fontWeight: 'var(--bar-fw)' }}
            >
              {loading ? p.stale : item.translation}
            </p>
          )}
        </div>
        <button
          type="button"
          tabIndex={-1}
          aria-label={t('bar.preview.collapse')}
          title={`${t('bar.preview.collapse')} (Alt+\`)`}
          onClick={p.onCollapse}
          className="inline-flex size-5 shrink-0 items-center justify-center rounded-sm text-fg-4 hover:bg-hover hover:text-fg-2"
        >
          <X className="size-3.5" strokeWidth={2} />
        </button>
      </div>
      {loading && p.stale && <span className="mx-3 h-px overflow-hidden bg-line-soft"><span className="skeleton block h-px w-full" /></span>}
      <div className="flex h-[30px] shrink-0 items-center gap-1 pl-9 pr-1.5 text-12">
        <span className="min-w-0 flex-1 truncate text-fg-3" lang="zh-CN">
          {item.text}
        </span>
        {failed && item.state === 'failed' ? (
          <Action icon={<RotateCw className="size-3" />} label={t('bar.ctx.retry')} onClick={() => p.onRetry?.(item.n)} />
        ) : (
          <>
            <Action icon={<CornerDownLeft className="size-3" />} label={t('bar.ctx.insert')} hint={`Alt+${item.n}`} disabled={!ok} onClick={() => p.onInsert?.(item.n)} />
            <Action icon={<Copy className="size-3" />} label={t('bar.ctx.copy')} disabled={!ok} onClick={() => p.onCopy?.(item.n)} />
          </>
        )}
      </div>
    </div>
  )
})

function Action({ icon, label, hint, disabled, onClick }: { icon: React.ReactNode; label: string; hint?: string; disabled?: boolean; onClick?: () => void }) {
  return (
    <button
      type="button"
      tabIndex={-1}
      disabled={disabled}
      onClick={onClick}
      className="inline-flex h-[22px] shrink-0 items-center gap-1 rounded-sm px-1.5 text-12 text-fg-2 transition-colors hover:bg-hover hover:text-fg disabled:text-fg-4 disabled:hover:bg-transparent"
    >
      {icon}
      {label}
      {hint && <span className="tnum text-11 text-fg-4">{hint}</span>}
    </button>
  )
}
