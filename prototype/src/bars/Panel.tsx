import { useLayoutEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import * as RCtx from '@radix-ui/react-context-menu'
import * as RMenu from '@radix-ui/react-dropdown-menu'
import { Check, ChevronDown, CircleAlert, Copy, CornerDownLeft, Pause, RotateCw } from 'lucide-react'
import { TARGETS, estimateWidth, type Item, type Target } from '../data/scenarios'
import { Kbd, cx } from '../ui/primitives'
import { POPPER, useScope } from '../ui/scope'
import { BarMenu, MoreButton, TARGET_CODE, bannerMeta, insertable, langAttr, toneText, type BarProps } from './common'

/**
 * The translation panel.
 * Vertical list: key chip · translation · original candidate, plus a 24px footer
 * (language pair / status · ⋯). Width fits content within [216, 320] px @13px and
 * only grows during one composition, so rows never jump while results arrive.
 */
export function Panel(p: BarProps) {
  const { t } = useTranslation()
  const { list, s, altHeld } = p
  const orig = s.showOriginal
  const meta = bannerMeta(list.banner)
  const fs = s.textSize
  const compact = s.density === 'compact'
  const rowH = Math.round(fs * (compact ? 1.85 : 2.15)) // 13px → 24 / 28
  const chip = compact ? 15 : 16
  const minW = Math.round(fs * 16.6) // 216
  const maxW = Math.round(fs * 24.6) // 320
  const bg = { background: `color-mix(in oklch, var(--bar-bg) ${Math.round(s.opacity * 100)}%, transparent)` }
  const quiet = list.banner === 'failed' || list.banner === 'auth'

  // Grow-only width per composition.
  const boxRef = useRef<HTMLDivElement>(null)
  const grown = useRef<{ key: unknown; w: number }>({ key: undefined, w: 0 })
  if (grown.current.key !== p.compositionKey) grown.current = { key: p.compositionKey, w: 0 }
  useLayoutEffect(() => {
    const w = boxRef.current?.offsetWidth ?? 0
    if (w > grown.current.w) grown.current.w = w
  })

  // Hover reports which row to preview; the lead preview (outside the panel) decides what to show.
  const hoverRow = (it: Item, el: HTMLElement | null) => {
    if (!el) return p.onHoverRow?.(undefined)
    const tr = el.querySelector<HTMLElement>('[data-tr]')
    const truncated = !!tr && tr.scrollWidth > tr.clientWidth + 1
    p.onHoverRow?.(it.n, truncated || it.state === 'failed' || it.state === 'noEntry')
  }
  // Report whether candidate 1 is cut off in its row (the trigger for the automatic lead preview).
  useLayoutEffect(() => {
    const tr = boxRef.current?.querySelector<HTMLElement>('[data-row="1"] [data-tr]')
    p.onLeadTruncated?.(!!tr && tr.scrollWidth > tr.clientWidth + 1)
  })

  if (list.banner === 'paused') {
    return (
      <div className="inline-flex flex-col rounded-xl shadow-bar backdrop-blur-md" style={{ ...bg, width: "max-content", minWidth: minW }}>
        <div className="flex items-center gap-2 px-2.5 text-13 text-fg-2" style={{ height: rowH + 8 }}>
          <Pause className="size-3.5 text-fg-3" strokeWidth={2.25} />
          <span className="flex-1 whitespace-nowrap pr-2">{t("bar.status.pausedLong")}</span>
          <span className="inline-flex gap-0.5">
            {s.shortcuts.pause.split('+').map((k) => (
              <Kbd key={k}>{k}</Kbd>
            ))}
          </span>
          <BarMenu {...p} s={s} open={p.menuOpen} trigger={<MoreButton label={t('bar.more')} className="-mr-1 size-[22px]" />} />
        </div>
      </div>
    )
  }

  return (
    <div className="relative inline-flex" onMouseLeave={() => p.onHoverRow?.(undefined)}>
      <div
        ref={boxRef}
        role="listbox"
        aria-label="Translations"
        className="flex flex-col rounded-xl shadow-bar backdrop-blur-md"
        style={{ ...bg, width: 'max-content', minWidth: Math.max(minW, grown.current.w), maxWidth: maxW }}
      >
        <div className="flex flex-col gap-px p-1">
          {list.items.map((it) => {
            const hovered = p.forceHover === it.n || p.hoverRow === it.n || p.ctxOpen === it.n
            const flashing = p.flash === it.n
            const row = (
              <button
                key={`${list.gen}-${it.n}`}
                data-row={it.n}
                type="button"
                role="option"
                aria-selected={flashing}
                tabIndex={-1}
                onMouseDown={(e) => e.button === 0 && e.preventDefault() /* keep focus in the app */}
                onMouseEnter={(e) => hoverRow(it, e.currentTarget)}
                onClick={() => (it.state === 'failed' ? p.onRetry?.(it.n) : p.onInsert?.(it.n))}
                className={cx(
                  'group flex w-full items-center gap-2 rounded-md pl-1.5 pr-2 text-left transition-colors duration-[var(--dur-1)]',
                  hovered && !flashing && 'bg-hover',
                  flashing && 'bg-accent-soft',
                  p.nudge === it.n && 'nudge',
                )}
                style={{ height: rowH }}
              >
                <span
                  className={cx(
                    'tnum inline-flex shrink-0 items-center justify-center rounded-xs text-11 font-semibold transition-colors duration-[var(--dur-1)]',
                    altHeld || flashing
                      ? 'bg-accent text-on-accent'
                      : hovered
                        ? 'bg-raised text-fg shadow-[inset_0_0_0_1px_var(--c-line-strong)]'
                        : 'bg-sunken text-fg-3 shadow-[inset_0_0_0_1px_var(--c-line-soft)]',
                  )}
                  style={{ width: chip, height: chip }}
                >
                  {it.n}
                </span>
                <span className="min-w-0 flex-1 pr-3">
                  <Slot it={it} fs={fs} target={s.target} flashing={flashing} quiet={quiet} t={t} />
                </span>
                {it.n === 1 && p.leadMore && (
                  <span className="shrink-0 rounded-xs px-1 text-11 text-fg-3 shadow-[inset_0_0_0_1px_var(--c-line-soft)]" title={t('bar.preview.more')}>
                    ⋯
                  </span>
                )}
                {(orig === 'always' || (orig === 'hover' && hovered)) && (
                  <span className={cx('ml-auto max-w-[28%] shrink-0 truncate text-12', hovered ? 'text-fg-2' : 'text-fg-3')} lang="zh-CN">
                    {it.text}
                  </span>
                )}
              </button>
            )
            return (
              <RowMenu key={`${list.gen}-${it.n}`} it={it} p={p}>
                {row}
              </RowMenu>
            )
          })}
        </div>

        <div className="flex h-6 items-center gap-1 border-t border-line-soft pl-1.5 pr-0.5 text-12">
          {meta ? (
            <span className={cx('flex min-w-0 items-center gap-1.5 pl-0.5', meta.tone === 'danger' ? 'text-danger-text' : 'text-fg-3')}>
              <meta.icon className={cx('size-3 shrink-0', toneText[meta.tone])} strokeWidth={2.25} />
              <span className="truncate">{t(meta.long)}</span>
            </span>
          ) : (
            <TargetSwitch target={s.target} onTarget={p.onTarget} />
          )}
          <span className="ml-auto" />
          <BarMenu {...p} s={s} open={p.menuOpen} trigger={<MoreButton label={t('bar.more')} className="size-5" />} />
        </div>
      </div>

    </div>
  )
}

/** Right-click: insert, copy, retry — same actions as Alt+N / Alt+Shift+N / click. */
function RowMenu({ it, p, children }: { it: Item; p: BarProps; children: React.ReactNode }) {
  const { t } = useTranslation()
  const { portal } = useScope()
  const ok = insertable(it)
  const item = 'flex h-7 cursor-default select-none items-center gap-2 rounded-sm px-2 text-13 outline-none data-[highlighted]:bg-hover data-[disabled]:text-fg-4'
  return (
    <RCtx.Root onOpenChange={(o) => p.onCtx?.(o ? it.n : undefined)} modal={false}>
      <RCtx.Trigger asChild>{children}</RCtx.Trigger>
      <RCtx.Portal container={portal}>
        <RCtx.Content avoidCollisions={POPPER.avoidCollisions} className="anim-pop z-50 min-w-[184px] rounded-lg bg-raised p-1 text-fg shadow-pop" onCloseAutoFocus={(e) => e.preventDefault()}>
          <RCtx.Item className={item} disabled={!ok} onSelect={() => p.onInsert?.(it.n)}>
            <CornerDownLeft className="size-3.5 text-fg-3" />
            <span className="flex-1">{t('bar.ctx.insert')}</span>
            <span className="text-12 text-fg-3 tnum">Alt+{it.n}</span>
          </RCtx.Item>
          <RCtx.Item className={item} disabled={!ok} onSelect={() => p.onCopy?.(it.n)}>
            <Copy className="size-3.5 text-fg-3" />
            <span className="flex-1">{t('bar.ctx.copy')}</span>
            <span className="text-12 text-fg-3 tnum">Alt+Shift+{it.n}</span>
          </RCtx.Item>
          {it.state === 'failed' && (
            <RCtx.Item className={item} onSelect={() => p.onRetry?.(it.n)}>
              <RotateCw className="size-3.5 text-fg-3" />
              <span className="flex-1">{t('bar.ctx.retry')}</span>
            </RCtx.Item>
          )}
        </RCtx.Content>
      </RCtx.Portal>
    </RCtx.Root>
  )
}

/** Footer language pair doubles as a quick target-language switch. */
function TargetSwitch({ target, onTarget }: { target: Target; onTarget?: (t: Target) => void }) {
  const { t } = useTranslation()
  const { portal } = useScope()
  return (
    <RMenu.Root modal={false}>
      <RMenu.Trigger asChild>
        <button
          type="button"
          tabIndex={-1}
          aria-label={t('bar.targetMenu')}
          onMouseDown={(e) => e.preventDefault()}
          className="flex h-5 items-center gap-1 rounded-sm px-1 text-fg-3 transition-colors hover:bg-hover hover:text-fg-2 data-[state=open]:bg-press data-[state=open]:text-fg"
        >
          <span className="size-1.5 rounded-full bg-success" />
          <span lang="zh-CN" className="ml-0.5">
            中
          </span>
          <span className="text-fg-4">→</span>
          <span>{TARGET_CODE[target]}</span>
          <ChevronDown className="size-3 opacity-70" strokeWidth={2} />
        </button>
      </RMenu.Trigger>
      <RMenu.Portal container={portal}>
        <RMenu.Content avoidCollisions={POPPER.avoidCollisions} side="bottom" align="start" sideOffset={6} className="anim-pop z-50 min-w-[168px] rounded-lg bg-raised p-1 text-fg shadow-pop" onCloseAutoFocus={(e) => e.preventDefault()}>
          <div className="px-2 pb-1 pt-0.5 text-12 text-fg-3">{t('bar.targetMenu')}</div>
          {TARGETS.map((x) => (
            <RMenu.Item
              key={x.id}
              onSelect={() => onTarget?.(x.id)}
              className="flex h-7 cursor-default select-none items-center gap-2 rounded-sm px-2 text-13 outline-none data-[highlighted]:bg-hover"
            >
              <span className="flex-1" lang={x.id}>
                {x.native}
              </span>
              {x.id === target && <Check className="size-3.5 text-accent-text" strokeWidth={2.25} />}
            </RMenu.Item>
          ))}
        </RMenu.Content>
      </RMenu.Portal>
    </RMenu.Root>
  )
}

function Slot({ it, fs, target, flashing, quiet, t }: { it: Item; fs: number; target: Target; flashing: boolean; quiet: boolean; t: (k: string) => string }) {
  if (it.state === 'loading' && it.prev)
    return (
      <span aria-busy aria-label={t('bar.loading')} lang={langAttr(target)} className="block truncate text-fg opacity-45" style={{ fontSize: fs, lineHeight: `${Math.round(fs * 1.4)}px`, fontWeight: 'var(--bar-fw)' }}>
        {it.prev}
      </span>
    )
  if (it.state === 'loading')
    return <span aria-label={t('bar.loading')} className="skeleton block h-[7px] rounded-full" style={{ width: `${estimateWidth(it.text, target)}ch`, fontSize: fs }} />
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
      data-tr
      lang={langAttr(target)}
      className={cx('block truncate', flashing ? 'text-accent-text' : 'text-fg')}
      style={{ fontSize: fs, lineHeight: `${Math.round(fs * 1.4)}px`, fontWeight: 'var(--bar-fw)' }}
    >
      {it.translation}
    </span>
  )
}
