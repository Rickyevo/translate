import type { ReactNode } from 'react'
import { useScope } from '../ui/scope'
import { cx } from '../ui/primitives'

/** Section: A = hairline group, B = card. Same content, different structure. */
export function Section({ title, desc, children, aside }: { title?: ReactNode; desc?: ReactNode; children: ReactNode; aside?: ReactNode }) {
  const { dir } = useScope()
  if (dir === 'a') {
    return (
      <section className="flex flex-col gap-2">
        {title && (
          <div className="flex items-end justify-between gap-4 px-0.5">
            <div>
              <h3 className="text-13 font-semibold text-fg">{title}</h3>
              {desc && <p className="text-12 text-fg-3">{desc}</p>}
            </div>
            {aside}
          </div>
        )}
        <div className="divide-y divide-line-soft overflow-hidden rounded-lg bg-surface shadow-[inset_0_0_0_1px_var(--c-line-soft)] [&>*]:border-line-soft">
          {children}
        </div>
      </section>
    )
  }
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
  const { dir } = useScope()
  return (
    <div
      className={cx(
        'flex gap-x-6',
        stack ? 'flex-col gap-y-2' : 'items-center justify-between',
        dir === 'a' ? 'min-h-[var(--row-h)] px-3.5 py-2.5' : 'min-h-[var(--row-h)] px-4 py-3',
        disabled && 'opacity-50',
      )}
    >
      <div className="min-w-0 flex-1">
        <label htmlFor={htmlFor} className={cx('block text-13 text-fg', dir === 'b' && 'font-medium')}>
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
  const { dir } = useScope()
  return (
    <header className={dir === 'a' ? 'mb-6' : 'mb-5'}>
      <h2 className={cx('font-semibold tracking-[-0.01em] text-fg', dir === 'a' ? 'text-18' : 'text-22')}>{title}</h2>
      {desc && <p className="mt-1 text-13 text-fg-3">{desc}</p>}
    </header>
  )
}
