import type { ReactNode } from 'react'
import { cx } from '../ui/primitives'

/** A settings section: a card with an optional heading inside it. */
export function Section({ title, desc, children, aside }: { title?: ReactNode; desc?: ReactNode; children: ReactNode; aside?: ReactNode }) {
  return (
    <section className="flex flex-col overflow-hidden rounded-xl bg-surface shadow-[var(--sh-control),0_0_0_1px_var(--c-line-soft)]">
      {title && (
        <div className="flex items-start justify-between gap-4 px-4 pb-1 pt-3.5">
          <div>
            <h3 className="text-14 font-semibold text-fg">{title}</h3>
            {desc && <p className="mt-0.5 text-12 text-fg-3">{desc}</p>}
          </div>
          {aside}
        </div>
      )}
      <div className="divide-y divide-line-soft [&>*]:border-line-soft">{children}</div>
    </section>
  )
}

export function Row({
  label,
  desc,
  control,
  children,
  htmlFor,
  stack,
  disabled,
}: {
  label: ReactNode
  desc?: ReactNode
  control?: ReactNode
  children?: ReactNode
  htmlFor?: string
  stack?: boolean
  disabled?: boolean
}) {
  return (
    <div data-row className={cx('flex min-h-[var(--row-h)] gap-x-6 px-4 py-3', stack ? 'flex-col gap-y-2' : 'items-center justify-between', disabled && 'opacity-50')}>
      <div className="min-w-0 flex-1">
        <label htmlFor={htmlFor} className="block text-13 font-medium text-fg">
          {label}
        </label>
        {desc && <p className="mt-px text-12 leading-[17px] text-fg-3">{desc}</p>}
      </div>
      {control && <div className="flex shrink-0 items-center gap-2">{control}</div>}
      {children}
    </div>
  )
}

export function PageHeader({ title, desc }: { title: ReactNode; desc?: ReactNode }) {
  return (
    <header className="mb-5">
      <h2 className="text-22 font-semibold tracking-[-0.01em] text-fg">{title}</h2>
      {desc && <p className="mt-1 text-13 text-fg-3">{desc}</p>}
    </header>
  )
}

/** Standard padding for free-form content inside a Section. */
export const PAD = 'px-4 py-3'
