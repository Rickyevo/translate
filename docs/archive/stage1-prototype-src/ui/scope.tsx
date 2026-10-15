import { createContext, useContext, useState, type CSSProperties, type ReactNode } from 'react'
import type { Dir, Theme } from '../store'

interface ScopeCtx {
  dir: Dir
  theme: Theme
  portal: HTMLElement | null
}
const Ctx = createContext<ScopeCtx>({ dir: 'a', theme: 'light', portal: null })
export const useScope = () => useContext(Ctx)

/** A token scope. Radix portals render into this scope so popovers inherit its theme. */
export function Scope({
  dir,
  theme,
  lang,
  className,
  style,
  children,
}: {
  dir: Dir
  theme: Theme
  lang?: string
  className?: string
  style?: CSSProperties
  children: ReactNode
}) {
  const [portal, setPortal] = useState<HTMLElement | null>(null)
  return (
    <Ctx.Provider value={{ dir, theme, portal }}>
      <div data-dir={dir} data-theme={theme} lang={lang} className={className} style={style}>
        {children}
        <div ref={setPortal} className="contents" />
      </div>
    </Ctx.Provider>
  )
}
