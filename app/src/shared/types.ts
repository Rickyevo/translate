/* Shapes shared by the main process and renderers (IPC payloads). */
import type { Settings } from '../../../prototype/src/model'
import type { CandidateList, Target } from '../../../prototype/src/data/scenarios'

export type ThemeName = 'light' | 'dark'
export type { EngineStatus, LinkId } from '../../../prototype/src/settings/bridge'
import type { EngineStatus, LinkId } from '../../../prototype/src/settings/bridge'

/** Everything the panel renderer needs; pushed by main on every change. */
export interface PanelState {
  list: CandidateList | null
  settings: Settings
  theme: ThemeName
  paused: boolean
  hidden: boolean
  composition: number
  /** One-line notice under the panel: an i18n key under `bar.` (+ interpolation). */
  notice?: { key: string; text?: string }
}

export interface PreviewPlacementMsg {
  kind: 'outer' | 'beside' | 'scroll' | 'overlay' | 'none'
  h: number
  w: number
  scroll: boolean
}

export type PanelKey = { action: 'togglePreview' } | { action: 'step'; d: 1 | -1 } | { action: 'scroll'; d: 1 | -1 } | { action: 'alt'; down: boolean }

export interface TranslateApi {
  // panel
  onState(cb: (s: PanelState) => void): void
  onKey(cb: (k: PanelKey) => void): void
  onPreviewPlacement(cb: (p: PreviewPlacementMsg) => void): void
  /** Content size, plus how far open menus (the row context menu) extend (from the content's top-left). */
  panelSize(w: number, h: number, extentW: number, extentH: number): void
  panelRows(rows: { n: number; x: number; y: number; w: number; h: number }[]): void
  mouseInside(win: 'panel' | 'preview', inside: boolean): void
  insert(gen: number, n: number): void
  copy(gen: number, n: number): void
  retry(gen: number, n: number): void
  previewNeed(need: { wanted: boolean; requested: boolean; w: number; h: number }): void
  // settings
  getSettings(): Promise<{ saved: Settings; theme: ThemeName; paused: boolean; version: string; status: EngineStatus }>
  saveSettings(s: Settings): Promise<void>
  draftSettings(s: Settings): void
  setPaused(p: boolean): void
  windowAction(a: 'close' | 'minimize'): void
  quit(): void
  onTheme(cb: (t: ThemeName) => void): void
  /** Pause state changed elsewhere (Ctrl+Alt+P). */
  onPaused(cb: (paused: boolean) => void): void
  // settings → backend (see prototype/src/settings/bridge.ts)
  svcTest(service: unknown, key: string): Promise<{ ok: boolean; ms?: number; error?: string; status?: number; detail?: string }>
  svcModels(service: unknown, key: string): Promise<{ ok: boolean; models?: string[]; error?: string; status?: number; detail?: string }>
  svcKeys(): Promise<Record<string, boolean>>
  cacheStats(): Promise<{ count: number; bytes: number }>
  cacheClear(): Promise<{ count: number; bytes: number }>
  statusGet(): Promise<EngineStatus>
  /** Pushed when an input method's connection or a shortcut's availability changes. */
  onStatus(cb: (s: EngineStatus) => void): void
  openLogs(): void
  /** While true, Translate's global shortcuts are released so a new one can be typed in Settings. */
  recordShortcut(on: boolean): Promise<void>
  /** Whether Windows would give Translate this shortcut (free, or already Translate's). */
  shortcutAvailable(accel: string): Promise<boolean>
  openLink(id: LinkId): void
}
