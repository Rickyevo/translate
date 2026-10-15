import { forwardRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode } from 'react'
import * as RSwitch from '@radix-ui/react-switch'
import * as RSelect from '@radix-ui/react-select'
import * as RSlider from '@radix-ui/react-slider'
import * as RTooltip from '@radix-ui/react-tooltip'
import * as RMenu from '@radix-ui/react-dropdown-menu'
import * as RRadio from '@radix-ui/react-radio-group'
import { Check, ChevronDown, CircleAlert, Info, TriangleAlert, CircleCheck } from 'lucide-react'
import { useScope } from './scope'

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ')

/* ------------------------------------------------------------------ Button */

type BtnVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
type BtnSize = 'sm' | 'md'
const btnBase =
  'focus-ring inline-flex items-center justify-center gap-1.5 whitespace-nowrap font-medium select-none ' +
  'transition-[background-color,box-shadow,color] duration-[var(--dur-1)] ' +
  'disabled:pointer-events-none'
const btnVariant: Record<BtnVariant, string> = {
  primary:
    'bg-accent text-on-accent hover:bg-accent-hover active:brightness-95 shadow-control disabled:bg-sunken disabled:text-fg-4 disabled:shadow-[inset_0_0_0_1px_var(--c-line-soft)]',
  secondary:
    'bg-raised text-fg shadow-[var(--sh-control),inset_0_0_0_1px_var(--c-line)] hover:bg-[color-mix(in_oklch,var(--c-raised),var(--c-fg)_4%)] active:bg-[color-mix(in_oklch,var(--c-raised),var(--c-fg)_7%)] disabled:opacity-45',
  ghost: 'text-fg-2 hover:bg-hover hover:text-fg active:bg-press disabled:opacity-45',
  danger:
    'bg-raised text-danger-text shadow-[var(--sh-control),inset_0_0_0_1px_var(--c-line)] hover:bg-danger-soft active:bg-danger-soft disabled:opacity-45',
}
const btnSize: Record<BtnSize, string> = {
  sm: 'h-6 px-2 text-12 rounded-sm',
  md: 'h-[var(--ctl-h)] px-3 text-13 rounded-md',
}

export const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: BtnVariant; size?: BtnSize; forceState?: 'hover' | 'pressed' | 'focus' }
>(function Button({ variant = 'secondary', size = 'md', className, forceState, ...p }, ref) {
  return (
    <button
      ref={ref}
      type="button"
      data-force={forceState}
      className={cx(btnBase, btnVariant[variant], btnSize[size], forceState && `force-${forceState}`, className)}
      {...p}
    />
  )
})

export const IconButton = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & { label: string; size?: 'sm' | 'md' }>(
  function IconButton({ label, size = 'md', className, children, ...p }, ref) {
    return (
      <button
        ref={ref}
        type="button"
        aria-label={label}
        title={label}
        className={cx(
          'focus-ring inline-flex items-center justify-center rounded-sm text-fg-3 hover:bg-hover hover:text-fg active:bg-press transition-colors duration-[var(--dur-1)]',
          size === 'sm' ? 'size-6' : 'size-7',
          className,
        )}
        {...p}
      >
        {children}
      </button>
    )
  },
)

/* ------------------------------------------------------------------ Kbd */

export function Kbd({ children, tone = 'default', className }: { children: ReactNode; tone?: 'default' | 'accent'; className?: string }) {
  return (
    <kbd
      className={cx(
        'inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-xs px-1 font-sans text-11 font-medium tnum',
        tone === 'accent' ? 'bg-accent text-on-accent' : 'bg-sunken text-fg-2 shadow-[inset_0_0_0_1px_var(--c-line)]',
        className,
      )}
    >
      {children}
    </kbd>
  )
}

export function Shortcut({ keys, className }: { keys: string; className?: string }) {
  return (
    <span className={cx('inline-flex items-center gap-0.5', className)}>
      {keys.split('+').map((k) => (
        <Kbd key={k}>{k}</Kbd>
      ))}
    </span>
  )
}

/* ------------------------------------------------------------------ Switch */

export function Switch({
  checked,
  onCheckedChange,
  disabled,
  label,
  id,
}: {
  checked: boolean
  onCheckedChange?: (v: boolean) => void
  disabled?: boolean
  label?: string
  id?: string
}) {
  return (
    <RSwitch.Root
      id={id}
      aria-label={label}
      checked={checked}
      disabled={disabled}
      onCheckedChange={onCheckedChange}
      className={cx(
        'focus-ring relative inline-flex h-[18px] w-[30px] shrink-0 items-center rounded-full transition-colors duration-[var(--dur-2)]',
        'bg-line-strong data-[state=checked]:bg-accent disabled:opacity-45',
      )}
    >
      <RSwitch.Thumb className="block size-[14px] translate-x-[2px] rounded-full bg-white shadow-[0_1px_2px_oklch(0_0_0/0.25)] transition-transform duration-[var(--dur-2)] ease-[var(--ease-out)] data-[state=checked]:translate-x-[14px]" />
    </RSwitch.Root>
  )
}

/* ------------------------------------------------------------------ Input */

export const TextInput = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean; suffix?: ReactNode; wrapClassName?: string; mono?: boolean }
>(function TextInput({ invalid, suffix, wrapClassName, className, mono, ...p }, ref) {
  return (
    <div
      className={cx(
        'group flex h-[var(--ctl-h)] items-center rounded-md bg-surface transition-shadow duration-[var(--dur-1)]',
        'shadow-[inset_0_0_0_1px_var(--c-line)] hover:shadow-[inset_0_0_0_1px_var(--c-line-strong)]',
        'focus-within:shadow-[inset_0_0_0_1px_var(--c-accent),0_0_0_3px_var(--c-accent-soft)]',
        invalid &&
          'shadow-[inset_0_0_0_1px_var(--c-danger)] hover:shadow-[inset_0_0_0_1px_var(--c-danger)] focus-within:shadow-[inset_0_0_0_1px_var(--c-danger),0_0_0_3px_var(--c-danger-soft)]',
        p.disabled && 'opacity-50',
        wrapClassName,
      )}
    >
      <input
        ref={ref}
        aria-invalid={invalid || undefined}
        className={cx(
          'h-full min-w-0 flex-1 bg-transparent px-2.5 text-13 text-fg outline-none placeholder:text-fg-4',
          mono && 'tnum tracking-[0.01em]',
          className,
        )}
        {...p}
      />
      {suffix && <div className="flex shrink-0 items-center pr-1">{suffix}</div>}
    </div>
  )
})

/* ------------------------------------------------------------------ Select */

export function Select<T extends string>({
  value,
  onValueChange,
  options,
  className,
  label,
}: {
  value: T
  onValueChange: (v: T) => void
  options: { value: T; label: ReactNode; hint?: ReactNode; lang?: string }[]
  className?: string
  label?: string
}) {
  const { portal } = useScope()
  const cur = options.find((o) => o.value === value)
  return (
    <RSelect.Root value={value} onValueChange={(v) => onValueChange(v as T)}>
      <RSelect.Trigger
        aria-label={label}
        className={cx(
          'focus-ring inline-flex h-[var(--ctl-h)] items-center justify-between gap-2 rounded-md bg-raised pl-2.5 pr-2 text-13 text-fg',
          'shadow-[var(--sh-control),inset_0_0_0_1px_var(--c-line)] hover:shadow-[var(--sh-control),inset_0_0_0_1px_var(--c-line-strong)]',
          'data-[state=open]:shadow-[inset_0_0_0_1px_var(--c-accent),0_0_0_3px_var(--c-accent-soft)]',
          className,
        )}
      >
        <span className="truncate" lang={cur?.lang}>
          {cur?.label}
        </span>
        <ChevronDown className="size-3.5 shrink-0 text-fg-3" strokeWidth={2} />
      </RSelect.Trigger>
      <RSelect.Portal container={portal}>
        <RSelect.Content
          position="popper"
          sideOffset={4}
          className="anim-pop z-50 min-w-[var(--radix-select-trigger-width)] overflow-hidden rounded-lg bg-raised p-1 text-fg shadow-pop"
        >
          <RSelect.Viewport>
            {options.map((o) => (
              <RSelect.Item
                key={o.value}
                value={o.value}
                className="relative flex h-[30px] cursor-default select-none items-center gap-2 rounded-sm pl-2 pr-7 text-13 outline-none data-[highlighted]:bg-hover"
              >
                <RSelect.ItemText>
                  <span lang={o.lang}>{o.label}</span>
                </RSelect.ItemText>
                {o.hint && <span className="ml-auto text-12 text-fg-3">{o.hint}</span>}
                <RSelect.ItemIndicator className="absolute right-2 inline-flex">
                  <Check className="size-3.5 text-accent-text" strokeWidth={2.25} />
                </RSelect.ItemIndicator>
              </RSelect.Item>
            ))}
          </RSelect.Viewport>
        </RSelect.Content>
      </RSelect.Portal>
    </RSelect.Root>
  )
}

/* ------------------------------------------------------------------ Segmented */

export function Segmented<T extends string>({
  value,
  onValueChange,
  options,
  label,
  className,
}: {
  value: T
  onValueChange: (v: T) => void
  options: { value: T; label: ReactNode; icon?: ReactNode }[]
  label?: string
  className?: string
}) {
  return (
    <RRadio.Root
      aria-label={label}
      value={value}
      onValueChange={(v) => onValueChange(v as T)}
      orientation="horizontal"
      className={cx('inline-flex h-[var(--ctl-h)] items-center gap-0.5 rounded-md bg-sunken p-0.5 shadow-[inset_0_0_0_1px_var(--c-line-soft)]', className)}
    >
      {options.map((o) => (
        <RRadio.Item
          key={o.value}
          value={o.value}
          className={cx(
            'focus-ring inline-flex h-full items-center gap-1.5 rounded-sm px-2.5 text-12 font-medium text-fg-3 transition-colors duration-[var(--dur-1)]',
            'hover:text-fg data-[state=checked]:bg-raised data-[state=checked]:text-fg data-[state=checked]:shadow-[var(--sh-control),inset_0_0_0_1px_var(--c-line-soft)]',
          )}
        >
          {o.icon}
          {o.label}
        </RRadio.Item>
      ))}
    </RRadio.Root>
  )
}

/* ------------------------------------------------------------------ Slider */

export function Slider({
  value,
  onValueChange,
  min,
  max,
  step,
  label,
  format,
  className,
}: {
  value: number
  onValueChange: (v: number) => void
  min: number
  max: number
  step: number
  label: string
  format?: (v: number) => string
  className?: string
}) {
  return (
    <div className={cx('flex items-center gap-3', className)}>
      <RSlider.Root
        aria-label={label}
        value={[value]}
        min={min}
        max={max}
        step={step}
        onValueChange={([v]) => onValueChange(v)}
        className="relative flex h-5 w-[140px] touch-none select-none items-center"
      >
        <RSlider.Track className="relative h-[3px] grow overflow-hidden rounded-full bg-line-strong">
          <RSlider.Range className="absolute h-full bg-accent" />
        </RSlider.Track>
        <RSlider.Thumb className="focus-ring block size-3.5 rounded-full bg-white shadow-[0_0_0_1px_var(--c-line-strong),0_1px_3px_oklch(0_0_0/0.2)] transition-transform hover:scale-110" />
      </RSlider.Root>
      <span className="w-10 text-right text-12 text-fg-2 tnum">{format ? format(value) : value}</span>
    </div>
  )
}

/* ------------------------------------------------------------------ Tooltip */

export function Tip({ content, children, side = 'top' }: { content: ReactNode; children: ReactNode; side?: 'top' | 'bottom' | 'left' | 'right' }) {
  const { portal } = useScope()
  return (
    <RTooltip.Root delayDuration={350}>
      <RTooltip.Trigger asChild>{children}</RTooltip.Trigger>
      <RTooltip.Portal container={portal}>
        <RTooltip.Content
          side={side}
          sideOffset={6}
          className="anim-fade z-50 max-w-[260px] rounded-sm bg-raised px-2 py-1 text-12 text-fg shadow-pop"
        >
          {content}
        </RTooltip.Content>
      </RTooltip.Portal>
    </RTooltip.Root>
  )
}

/* ------------------------------------------------------------------ Menu */

export const Menu = RMenu.Root
export const MenuTrigger = RMenu.Trigger
export function MenuContent({ children, align = 'end', side = 'bottom' }: { children: ReactNode; align?: 'start' | 'end'; side?: 'top' | 'bottom' }) {
  const { portal } = useScope()
  return (
    <RMenu.Portal container={portal}>
      <RMenu.Content
        align={align}
        side={side}
        sideOffset={6}
        className="anim-pop z-50 min-w-[208px] rounded-lg bg-raised p-1 text-fg shadow-pop"
        onCloseAutoFocus={(e) => e.preventDefault()}
      >
        {children}
      </RMenu.Content>
    </RMenu.Portal>
  )
}
export function MenuItem({
  icon,
  children,
  shortcut,
  onSelect,
  danger,
  forceHighlight,
}: {
  icon?: ReactNode
  children: ReactNode
  shortcut?: string
  onSelect?: () => void
  danger?: boolean
  forceHighlight?: boolean
}) {
  return (
    <RMenu.Item
      onSelect={onSelect}
      data-highlighted={forceHighlight ? '' : undefined}
      className={cx(
        'flex h-[30px] cursor-default select-none items-center gap-2 rounded-sm px-2 text-13 outline-none',
        'data-[highlighted]:bg-hover',
        danger ? 'text-danger-text' : 'text-fg',
      )}
    >
      {icon && <span className={cx('inline-flex size-4 items-center justify-center', danger ? '' : 'text-fg-3')}>{icon}</span>}
      <span className="flex-1">{children}</span>
      {shortcut && <span className="text-12 text-fg-3 tnum">{shortcut}</span>}
    </RMenu.Item>
  )
}
export const MenuSeparator = () => <RMenu.Separator className="mx-1 my-1 h-px bg-line-soft" />

/* ------------------------------------------------------------------ Message */

export function Message({
  tone,
  children,
  action,
  className,
}: {
  tone: 'info' | 'success' | 'warning' | 'danger'
  children: ReactNode
  action?: ReactNode
  className?: string
}) {
  const Icon = { info: Info, success: CircleCheck, warning: TriangleAlert, danger: CircleAlert }[tone]
  const color = {
    info: 'text-fg-3',
    success: 'text-success',
    warning: 'text-warning',
    danger: 'text-danger',
  }[tone]
  const bg = {
    info: 'bg-sunken',
    success: 'bg-sunken',
    warning: 'bg-warning-soft',
    danger: 'bg-danger-soft',
  }[tone]
  return (
    <div role={tone === 'danger' ? 'alert' : 'status'} className={cx('flex items-start gap-2 rounded-md px-3 py-2 text-13', bg, className)}>
      <Icon className={cx('mt-[3px] size-3.5 shrink-0', color)} strokeWidth={2} />
      <div className="min-w-0 flex-1 text-fg-2">{children}</div>
      {action}
    </div>
  )
}
