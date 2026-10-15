import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { EyeOff, Pause, Play, Power, Settings2, Search } from 'lucide-react'
import { Button, Kbd, Message, Segmented, Select, Slider, Switch, TextInput, cx } from '../ui/primitives'

const SWATCHES: [string, string][] = [
  ['app', '--c-app'],
  ['side', '--c-side'],
  ['surface', '--c-surface'],
  ['raised', '--c-raised'],
  ['sunken', '--c-sunken'],
  ['hover', '--c-hover'],
  ['line-soft', '--c-line-soft'],
  ['line', '--c-line'],
  ['line-strong', '--c-line-strong'],
  ['fg', '--c-fg'],
  ['fg-2', '--c-fg-2'],
  ['fg-3', '--c-fg-3'],
  ['fg-4', '--c-fg-4'],
  ['accent', '--c-accent'],
  ['accent-soft', '--c-accent-soft'],
  ['accent-text', '--c-accent-text'],
  ['danger', '--c-danger'],
  ['warning', '--c-warning'],
  ['success', '--c-success'],
]

const TYPE: { name: string; cls: string; spec: string }[] = [
  { name: 'Title', cls: 'text-22 font-semibold tracking-[-0.01em]', spec: '22/28 · 600' },
  { name: 'Page title', cls: 'text-18 font-semibold tracking-[-0.01em]', spec: '18/24 · 600' },
  { name: 'Section', cls: 'text-14 font-semibold', spec: '14/20 · 600' },
  { name: 'Body', cls: 'text-13', spec: '13/20 · 400' },
  { name: 'Label', cls: 'text-13 font-medium', spec: '13/20 · 500' },
  { name: 'Secondary', cls: 'text-12 text-fg-3', spec: '12/16 · 400' },
  { name: 'Caption / key', cls: 'text-11 font-medium text-fg-3', spec: '11/16 · 500' },
]

const SAMPLES: [string, string][] = [
  ['zh-CN', '用四种语言排印的界面 翻译栏 0123'],
  ['en', 'Translate types in four languages 0123'],
  ['ja', '4 つの言語で組まれたインターフェース'],
  ['ko', '네 가지 언어로 조판한 인터페이스'],
]

export function Showcase() {
  const { t } = useTranslation()
  const [sw, setSw] = useState(true)
  const [seg, setSeg] = useState<'hover' | 'always' | 'never'>('hover')
  const [sl, setSl] = useState(0.92)
  const [sel, setSel] = useState('en')
  return (
    <div className="scroll-quiet min-h-0 flex-1 overflow-auto bg-app">
      <div className="mx-auto grid max-w-[1120px] grid-cols-2 gap-x-10 gap-y-10 px-8 py-7">
        <Block title={t('showcase.type')} wide>
          <div className="grid grid-cols-[1fr_1fr] gap-x-10">
            <div className="flex flex-col gap-2.5">
              {TYPE.map((x) => (
                <div key={x.name} className="flex items-baseline gap-4">
                  <span className="w-[92px] shrink-0 text-11 text-fg-4 tnum">{x.spec}</span>
                  <span className={cx('text-fg', x.cls)}>{x.name}</span>
                </div>
              ))}
            </div>
            <div className="flex flex-col gap-2.5">
              {SAMPLES.map(([l, s]) => (
                <div key={l} lang={l} className="flex items-baseline gap-4">
                  <span className="w-[44px] shrink-0 text-11 text-fg-4">{l}</span>
                  <span className="text-14 text-fg">{s}</span>
                </div>
              ))}
              <div className="flex items-baseline gap-4" lang="en">
                <span className="w-[44px] shrink-0 text-11 text-fg-4">bar</span>
                <span className="text-13 font-[450] text-fg">Let's discuss this question again tomorrow</span>
              </div>
            </div>
          </div>
        </Block>

        <Block title={t('showcase.colors')} wide>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(96px,1fr))] gap-2">
            {SWATCHES.map(([n, v]) => (
              <div key={n} className="flex flex-col gap-1">
                <div className="h-10 rounded-md shadow-[inset_0_0_0_1px_var(--c-line-soft)]" style={{ background: `var(${v})` }} />
                <span className="text-11 text-fg-3">{n}</span>
              </div>
            ))}
          </div>
        </Block>

        <Block title={t('showcase.buttons')}>
          <StateGrid
            cols={[t('showcase.primary'), t('showcase.secondary'), t('showcase.ghost'), t('showcase.danger')]}
            rows={[
              ['Default', ['', '', '', '']],
              [t('showcase.hover'), ['!bg-accent-hover', '!bg-[color-mix(in_oklch,var(--c-raised),var(--c-fg)_4%)]', '!bg-hover !text-fg', '!bg-danger-soft']],
              [t('showcase.pressed'), ['!bg-accent-hover brightness-95', '!bg-[color-mix(in_oklch,var(--c-raised),var(--c-fg)_7%)]', '!bg-press !text-fg', '!bg-danger-soft brightness-95']],
              [t('showcase.focus'), ['outline-2 outline-offset-1 outline-[var(--c-focus)] outline', 'outline-2 outline-offset-1 outline-[var(--c-focus)] outline', 'outline-2 outline-offset-1 outline-[var(--c-focus)] outline', 'outline-2 outline-offset-1 outline-[var(--c-focus)] outline']],
              [t('showcase.disabled'), ['', '', '', '']],
            ]}
            render={(ci, cls, ri) => (
              <Button variant={(['primary', 'secondary', 'ghost', 'danger'] as const)[ci]} className={cls} disabled={ri === 4}>
                {t('settings.footer.save')}
              </Button>
            )}
          />
        </Block>

        <Block title={t('showcase.inputs')}>
          <div className="grid grid-cols-[72px_1fr] items-center gap-x-4 gap-y-2.5 text-12 text-fg-3">
            <span>Default</span>
            <TextInput defaultValue="https://api.openai.com/v1" />
            <span>{t('showcase.focus')}</span>
            <TextInput defaultValue="gpt-4o-mini" wrapClassName="!shadow-[inset_0_0_0_1px_var(--c-accent),0_0_0_3px_var(--c-accent-soft)]" />
            <span>{t('showcase.error')}</span>
            <div className="flex flex-col gap-1">
              <TextInput defaultValue="sk-bad-key" invalid mono />
              <span className="text-12 text-danger-text">{t('settings.translation.err.auth')}</span>
            </div>
            <span>{t('showcase.disabled')}</span>
            <TextInput defaultValue="Local-only mode" disabled />
            <span>Search</span>
            <TextInput placeholder={t('settings.search')} suffix={<Search className="mr-1.5 size-3.5 text-fg-4" />} />
          </div>
        </Block>

        <Block title={t('showcase.toggles')}>
          <div className="grid grid-cols-[72px_1fr] items-center gap-x-4 gap-y-3 text-12 text-fg-3">
            <span>Switch</span>
            <div className="flex items-center gap-4">
              <Switch checked={sw} onCheckedChange={setSw} label="demo" />
              <Switch checked={false} label="off" />
              <Switch checked disabled label="disabled on" />
              <Switch checked={false} disabled label="disabled off" />
            </div>
            <span>Segmented</span>
            <Segmented className="justify-self-start" value={seg} onValueChange={setSeg} options={(['hover', 'always', 'never'] as const).map((v) => ({ value: v, label: t(`settings.appearance.orig.${v}`) }))} />
            <span>Slider</span>
            <Slider label="opacity" value={sl} min={0.7} max={1} step={0.01} onValueChange={setSl} format={(v) => `${Math.round(v * 100)}%`} />
            <span>Select</span>
            <Select
              value={sel}
              onValueChange={setSel}
              className="w-[180px]"
              options={[
                { value: 'en', label: 'English', lang: 'en' },
                { value: 'ja', label: '日本語', lang: 'ja' },
                { value: 'ko', label: '한국어', lang: 'ko' },
              ]}
            />
            <span>Keys</span>
            <div className="flex items-center gap-3">
              <span className="inline-flex gap-0.5">
                <Kbd>Ctrl</Kbd>
                <Kbd>Alt</Kbd>
                <Kbd>O</Kbd>
              </span>
              <Kbd tone="accent">3</Kbd>
            </div>
          </div>
        </Block>

        <Block title={t('showcase.messages')}>
          <div className="flex flex-col gap-2">
            <Message tone="success">{t('showcase.info')}</Message>
            <Message tone="info">{t('bar.status.localOnlyLong')}</Message>
            <Message tone="warning">{t('showcase.warn')}</Message>
            <Message tone="danger" action={<Button size="sm">{t('bar.menu.settings').replace('…', '')}</Button>}>
              {t('showcase.errMsg')}
            </Message>
          </div>
        </Block>

        <Block title={t('showcase.menus')}>
          <div className="flex items-start gap-6">
            <StaticMenu
              items={[
                [<Pause key="p" className="size-3.5" />, t('bar.menu.pause'), 'Ctrl+Alt+P'],
                [<EyeOff key="h" className="size-3.5" />, t('bar.menu.hide'), 'Alt+0', true],
                [<Settings2 key="s" className="size-3.5" />, t('bar.menu.settings'), 'Ctrl+Alt+O'],
                null,
                [<Power key="q" className="size-3.5" />, t('bar.menu.quit')],
              ]}
            />
            <StaticMenu items={[[<Play key="r" className="size-3.5" />, t('bar.menu.resume'), 'Ctrl+Alt+P', true], null, [<Power key="q" className="size-3.5" />, t('bar.menu.quit')]]} />
          </div>
        </Block>

        <Block title={t('showcase.states')}>
          <div className="flex flex-col gap-1 rounded-lg bg-side p-2">
            <NavSample label={t('settings.nav.general')} />
            <NavSample label={t('settings.nav.translation')} hover />
            <NavSample label={t('settings.nav.appearance')} selected />
            <NavSample label={t('settings.nav.privacy')} focus />
          </div>
          <p className="mt-2 text-12 text-fg-3">
            Navigation: default, hover, selected (raised + accent icon), keyboard focus.
          </p>
        </Block>
      </div>
    </div>
  )
}

function Block({ title, children, wide }: { title: string; children: ReactNode; wide?: boolean }) {
  return (
    <section className={cx('flex flex-col gap-3', wide && 'col-span-2')}>
      <h3 className="border-b border-line-soft pb-2 text-13 font-semibold text-fg">{title}</h3>
      {children}
    </section>
  )
}

function StateGrid({ cols, rows, render }: { cols: string[]; rows: [string, string[]][]; render: (ci: number, cls: string, ri: number) => ReactNode }) {
  return (
    <div className="grid items-center gap-x-3 gap-y-2" style={{ gridTemplateColumns: `72px repeat(${cols.length}, auto)` }}>
      <span />
      {cols.map((c) => (
        <span key={c} className="text-11 text-fg-4">
          {c}
        </span>
      ))}
      {rows.map(([label, classes], ri) => (
        <Fragment2 key={label}>
          <span className="text-12 text-fg-3">{label}</span>
          {classes.map((cls, ci) => (
            <div key={ci}>{render(ci, cls, ri)}</div>
          ))}
        </Fragment2>
      ))}
    </div>
  )
}
const Fragment2 = ({ children }: { children: ReactNode }) => <>{children}</>

function StaticMenu({ items }: { items: ([ReactNode, string, string?, boolean?] | null)[] }) {
  return (
    <div className="h-max w-max min-w-[220px] rounded-lg bg-raised p-1 shadow-pop">
      {items.map((it, i) =>
        it ? (
          <div key={i} className={cx('flex h-[30px] items-center gap-2 rounded-sm px-2 text-13 text-fg', it[3] && 'bg-hover')}>
            <span className="inline-flex size-4 items-center justify-center text-fg-3">{it[0]}</span>
            <span className="flex-1 whitespace-nowrap pr-4">{it[1]}</span>
            {it[2] && <span className="text-12 text-fg-3 tnum">{it[2]}</span>}
          </div>
        ) : (
          <div key={i} className="mx-1 my-1 h-px bg-line-soft" />
        ),
      )}
    </div>
  )
}

function NavSample({ label, hover, selected, focus }: { label: string; hover?: boolean; selected?: boolean; focus?: boolean }) {
  return (
    <div
      className={cx(
        'flex items-center gap-2 px-2 text-13',
        'h-8 rounded-md font-medium',
        hover && 'bg-hover text-fg',
        selected && 'bg-surface text-fg shadow-[var(--sh-control),0_0_0_1px_var(--c-line-soft)]',
        focus && 'outline outline-2 outline-offset-1 outline-[var(--c-focus)]',
        !hover && !selected && 'text-fg-2',
      )}
    >
      <Settings2 className={cx('size-3.5', selected ? 'text-accent-text' : 'text-fg-3')} />
      {label}
    </div>
  )
}
