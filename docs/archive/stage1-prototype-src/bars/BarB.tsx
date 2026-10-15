import { useTranslation } from 'react-i18next'
import { CircleAlert, Pause } from 'lucide-react'
import { estimateWidth } from '../data/scenarios'
import { Kbd, cx } from '../ui/primitives'
import { BarMenu, MoreButton, PeekBody, TARGET_CODE, bannerMeta, insertable, langAttr, toneText, usePeek, type BarProps } from './common'

/**
 * Direction B — Panel.
 * A vertical list that pairs every translation with its key and its source
 * candidate, plus a fixed status footer. More context, larger footprint.
 */
export function BarB(p: BarProps) {
  const { t } = useTranslation()
  const { list, s, altHeld } = p
  const { peek, enter, leave } = usePeek(p.forcePeek)
  const orig = s.showOriginal === 'default' ? 'always' : s.showOriginal
  const meta = bannerMeta(list.banner)
  const fs = s.textSize
  const rowH = Math.round(fs * 2.45) // 13px → 32px
  const width = Math.round(fs * 23) // 13px → 300px
  const bg = { background: `color-mix(in oklch, var(--bar-bg) ${Math.round(s.opacity * 100)}%, transparent)` }
  const item = peek != null ? list.items.find((i) => i.n === peek) : undefined
  const peekLeft = p.edge === 'right'

  const footer = (
    <div className="flex h-[26px] items-center gap-1.5 border-t border-line-soft pl-2 pr-0.5 text-12">
      {meta ? (
        <span className={cx('flex min-w-0 items-center gap-1.5', meta.tone === 'danger' ? 'text-danger-text' : 'text-fg-3')}>
          <meta.icon className={cx('size-3 shrink-0', toneText[meta.tone])} strokeWidth={2.25} />
          <span className="truncate">{t(meta.long)}</span>
        </span>
      ) : (
        <span className="flex items-center gap-1.5 text-fg-3">
          <span className="size-1.5 rounded-full bg-success" />
          <span lang="zh-CN">中</span>
          <span className="text-fg-4">→</span>
          <span>{TARGET_CODE[s.target]}</span>
        </span>
      )}
      <span className="ml-auto" />
      <BarMenu {...p} s={s} open={p.menuOpen} trigger={<MoreButton label={t('bar.more')} className="size-[22px]" />} />
    </div>
  )

  if (list.banner === 'paused') {
    return (
      <div className="flex flex-col overflow-hidden rounded-xl p-1 shadow-bar backdrop-blur-md" style={{ ...bg, width }}>
        <div className="flex items-center gap-2 px-2 text-13 text-fg-2" style={{ height: rowH }}>
          <Pause className="size-3.5 text-fg-3" strokeWidth={2.25} />
          <span className="flex-1">{t('bar.status.pausedLong')}</span>
          <span className="inline-flex gap-0.5">
            {s.shortcuts.pause.split('+').map((k) => (
              <Kbd key={k}>{k}</Kbd>
            ))}
          </span>
        </div>
        <div className="-mx-1 -mb-1 px-1">
          <div className="flex h-[26px] items-center justify-end border-t border-line-soft pr-0.5">
            <BarMenu {...p} s={s} open={p.menuOpen} trigger={<MoreButton label={t('bar.more')} className="size-[22px]" />} />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="relative inline-flex" onMouseLeave={leave}>
      <div role="listbox" aria-label="Translations" className="flex flex-col rounded-xl shadow-bar backdrop-blur-md" style={{ ...bg, width }}>
        <div className="flex flex-col gap-px p-1">
          {list.items.map((it) => {
            const hovered = p.forceHover === it.n || peek === it.n
            const flashing = p.flash === it.n
            return (
              <button
                key={`${list.gen}-${it.n}`}
                type="button"
                role="option"
                aria-selected={flashing}
                tabIndex={-1}
                onMouseDown={(e) => e.preventDefault()}
                onMouseEnter={() => enter(it.n)}
                onClick={() => (insertable(it) ? p.onInsert?.(it.n) : it.state === 'failed' ? p.onRetry?.(it.n) : p.onInsert?.(it.n))}
                className={cx(
                  'flex items-center gap-2.5 rounded-md pl-1.5 pr-2 text-left transition-colors duration-[var(--dur-1)]',
                  hovered && !flashing && 'bg-hover',
                  flashing && 'bg-accent-soft',
                  p.nudge === it.n && 'nudge',
                )}
                style={{ height: rowH }}
              >
                <span
                  className={cx(
                    'tnum inline-flex size-[18px] shrink-0 items-center justify-center rounded-xs text-11 font-semibold transition-colors duration-[var(--dur-1)]',
                    altHeld || flashing
                      ? 'bg-accent text-on-accent'
                      : hovered
                        ? 'bg-raised text-fg shadow-[inset_0_0_0_1px_var(--c-line-strong)]'
                        : 'bg-sunken text-fg-3 shadow-[inset_0_0_0_1px_var(--c-line-soft)]',
                  )}
                >
                  {it.n}
                </span>
                <span className="min-w-0 flex-1">
                  <Slot it={it} fs={fs} target={s.target} flashing={flashing} quiet={list.banner === 'failed' || list.banner === 'auth'} t={t} />
                </span>
                {(orig === 'always' || (orig === 'hover' && hovered)) && (
                  <span className="max-w-[32%] shrink-0 truncate text-12 text-fg-3" lang="zh-CN">
                    {it.text}
                  </span>
                )}
              </button>
            )
          })}
        </div>
        {footer}
      </div>

      {item && (
        <div
          className={cx(
            'anim-pop absolute z-20 w-[240px] rounded-lg bg-raised px-3 py-2.5 shadow-pop',
            peekLeft ? 'right-full mr-1.5' : 'left-full ml-1.5',
          )}
          style={{ top: 4 + (item.n - 1) * (rowH + 1), ['--pop-from' as string]: '0px' }}
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
    return <span aria-label={t('bar.loading')} className="skeleton block h-[8px] rounded-full" style={{ width: `${estimateWidth(it.text, target)}ch`, fontSize: fs }} />
  if (it.state === 'failed')
    return (
      <span className={cx('flex items-center gap-1.5 whitespace-nowrap text-12', quiet ? 'text-fg-3' : 'text-danger-text')}>
        <CircleAlert className="size-3 text-danger" strokeWidth={2.25} />
        {t('bar.failed')}
      </span>
    )
  if (it.state === 'noEntry') return <span className="whitespace-nowrap text-12 text-fg-4">{t('bar.noEntry')}</span>
  return (
    <span
      lang={langAttr(target)}
      className={cx('block truncate', flashing ? 'text-accent-text' : 'text-fg')}
      style={{ fontSize: fs, lineHeight: `${Math.round(fs * 1.4)}px`, fontWeight: 'var(--bar-fw)' }}
    >
      {it.translation}
    </span>
  )
}
