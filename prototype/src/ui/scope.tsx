import { createContext, useContext, useState, type CSSProperties, type ReactNode } from 'react'
import type { Theme } from '../store'

interface ScopeCtx {
  theme: Theme
  portal: HTMLElement | null
}
const Ctx = createContext<ScopeCtx>({ theme: 'light', portal: null })
export const useScope = () => useContext(Ctx)

/** Popover collision handling. In a browser page, keep popovers inside the viewport.
 * In the app, the panel window grows to fit an open menu, so menus open where designed. */
export const POPPER = { avoidCollisions: true }

/** A token scope. Radix portals render into this scope so popovers inherit its theme. */
export function Scope({ theme, lang, className, style, children }: { theme: Theme; lang?: string; className?: string; style?: CSSProperties; children: ReactNode }) {
  const [portal, setPortal] = useState<HTMLElement | null>(null)
  return (
    <Ctx.Provider value={{ theme, portal }}>
      <div data-theme={theme} lang={lang} className={className} style={style}>
        {children}
        <div ref={setPortal} className="contents" />
      </div>
    </Ctx.Provider>
  )
}
