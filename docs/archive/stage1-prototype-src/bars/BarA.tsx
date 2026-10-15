import { useLayoutEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { CircleAlert, Pause } from 'lucide-react'
import { estimateWidth } from '../data/scenarios'
import { Kbd, cx } from '../ui/primitives'
import { BarMenu, MoreButton, PeekBody, bannerMeta, insertable, langAttr, toneText, usePeek, type BarProps } from './common'

/**
 * Direction A — Ribbon.
 * One horizontal line that reads like a continuation of the IME candidate row:
 * number + translation, nothing else until you ask (hover) for more.
 */
export function BarA(p: BarProps) {
  const { t } = useTranslation()
  const { list, s, altHeld } = p
  const { peek, enter, leave } = usePeek(p.forcePeek)
  const orig = s.showOriginal === 'default' ? 'hover' : s.showOriginal
  const meta = bannerMeta(list.banner)
  const barRef = useRef<HTMLDivElement>(null)
  const [peekX, setPeekX] = useState(0)
  const fs = s.textSize
  const h = Math.round(fs * 2.3) // 13px → 30px

  // Anchor the peek under the hovered item, clamped to the bar's left edge.
  useLayoutEffect(() => {
    if (peek == null || !barRef.current) return
    const el = barRef.current.querySelector<HTMLElement>(`[data-n="${peek}"]`)
    if (el) setPeekX(el.offsetLeft)
  }, [peek, list.gen])

  const bg = { background: `color-mix(in oklch, var(--bar-bg) ${Math.round(s.opacity * 100)}%, transparent)` }

  if (list.banner === 'paused') {
    return (
      <div className="inline-flex items-center gap-2 rounded-lg pl-2.5 pr-1 text-12 text-fg-2 shadow-bar backdrop-blur-md" style={{ ...bg, height: h }}>
        <Pause className="size-3 text-fg-3" strokeWidth={2.25} />
        <span>{t('bar.status.pausedLong')}</span>
        <span className="inline-flex items-center gap-0.5 text-fg-3">
          {s.shortcuts.pause.split('+').map((k) => (
            <Kbd key={k}>{k}</Kbd>
          ))}
        </span>
        <BarMenu {...p} s={s} open={p.menuOpen} trigger={<MoreButton label={t('bar.more')} className="size-6" />} />
      </div>
    )
  }

  const item = peek != null ? list.items.find((i) => i.n === peek) : undefined

  return (
    <div className="relative inline-flex flex-col" onMouseLeave={leave}>
      <div
        ref={barRef}
        role="listbox"
        aria-label="Translations"
        className="relative inline-flex items-center gap-px rounded-lg p-[3px] shadow-bar backdrop-blur-md"
        style={{ ...bg, height: h }}
      >
        {list.items.map((it) => {
          const hovered = p.forceHover === it.n || peek === it.n
          const flashing = p.flash === it.n
          return (
            <button
              key={`${list.gen}-${it.n}`}
              data-n={it.n}
              type="button"
              role="option"
              aria-selected={flashing}
              tabIndex={-1}
              onMouseDown={(e) => e.preventDefault()}
              onMouseEnter={() => enter(it.n)}
              onClick={() => (insertable(it) ? p.onInsert?.(it.n) : it.state === 'failed' ? p.onRetry?.(it.n) : p.onInsert?.(it.n))}
              className={cx(
                'group relative flex h-full min-w-0 items-center gap-[6px] rounded-sm px-[7px] transition-colors duration-[var(--dur-1)]',
                hovered && !flashing && 'bg-hover',
                flashing && 'bg-accent-soft',
                p.nudge === it.n && 'nudge',
              )}
            >
              <span
                className={cx(
                  'tnum shrink-0 text-11 font-medium transition-colors duration-[var(--dur-1)]',
                  altHeld ? 'font-semibold text-accent-text' : hovered ? 'text-fg-2' : 'text-fg-3',
                )}
              >
                {it.n}
              </span>
              <Slot it={it} fs={fs} target={s.target} flashing={flashing} quiet={list.banner === 'failed' || list.banner === 'auth'} t={t} />
              {orig === 'always' && it.state !== 'loading' && (
                <span className="shrink-0 text-12 text-fg-3" lang="zh-CN">
                  {it.text}
                </span>
              )}
            </button>
          )
        })}
        {meta && (
          <>
            <span className="mx-1 h-3.5 w-px shrink-0 bg-line" />
            <span className={cx('flex shrink-0 items-center gap-1 pl-0.5 pr-1 text-12', meta.tone === 'danger' ? 'text-danger-text' : 'text-fg-3')}>
              <meta.icon className={cx('size-3', toneText[meta.tone])} strokeWidth={2.25} />
              {t(meta.short)}
            </span>
          </>
        )}
        <BarMenu {...p} s={s} open={p.menuOpen} trigger={<MoreButton label={t('bar.more')} className="ml-px size-6" />} />
      </div>

      {item && (
        <div
          className={cx(
            'anim-pop absolute z-20 w-max min-w-[180px] max-w-[300px] rounded-lg bg-raised px-3 py-2.5 shadow-pop',
            p.placement === 'above' ? 'bottom-full mb-1.5' : 'top-full mt-1.5',
          )}
          style={{ left: Math.max(0, peekX), ['--pop-from' as string]: p.placement === 'above' ? '3px' : '-3px' }}
          onMouseEnter={() => enter(item.n)}
        >
          <PeekBody item={item} s={s} showOriginal={orig !== 'never'} />
        </div>
      )}
    </div>
  )
}

function Slot({ it, fs, target, flashing, quiet, t }: { it: BarProps['list']['items'][number]; fs: number; target: BarProps['s']['target']; flashing: boolean; quiet?: boolean; t: (k: string) => string }) {
  if (it.state === 'loading')
    return <span aria-label={t('bar.loading')} className="skeleton block h-[7px] rounded-full" style={{ width: `${estimateWidth(it.text, target)}ch`, fontSize: fs }} />
  // When the status already names the cause, each failed item is just a mark.
  if (it.state === 'failed' && quiet) return <CircleAlert aria-label={t('bar.failed')} className="size-3 text-danger" strokeWidth={2.25} />
  if (it.state === 'failed')
    return (
      <span className="flex items-center gap-1 whitespace-nowrap text-12 text-fg-3">
        <CircleAlert className="size-3 text-danger" strokeWidth={2.25} />
        {t('bar.failed')}
      </span>
    )
  if (it.state === 'noEntry') return <span className="whitespace-nowrap text-12 text-fg-4">{t('bar.noEntry')}</span>
  return (
    <span
      lang={langAttr(target)}
      className={cx('max-w-[200px] truncate', flashing ? 'text-accent-text' : 'text-fg')}
      style={{ fontSize: fs, lineHeight: `${Math.round(fs * 1.4)}px`, fontWeight: 'var(--bar-fw)' }}
    >
      {it.translation}
    </span>
  )
}
