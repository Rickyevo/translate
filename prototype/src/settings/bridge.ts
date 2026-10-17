/* Settings ↔ app bridge. The app's settings window installs real implementations (host → engine);
 * the design prototype leaves it null and the pages fall back to their simulated behaviour. */
import { create } from 'zustand'
import type { ProviderId, serviceOf } from '../model'

export type ServiceDraft = ReturnType<typeof serviceOf> & { jsonMode?: boolean }
export type TestResult = { ok: true; ms: number } | { ok: false; error: string; status?: number; detail?: string }
/** Destinations the host opens; the page never passes a URL or path. */
export type LinkId = 'home' | 'releases' | 'issues' | 'notices' | 'license'

/** What the host pushes to Settings when it changes: each input method's adapter state (connected · waiting ·
 *  starting · failed; absent = not running in the saved mode) and the global shortcuts Windows wouldn't give us. */
export interface EngineStatus {
  imeStates?: Record<string, string>
  hotkeysUnavailable?: string[]
}

export interface SettingsBridge {
  /** Real request with the draft settings; `key` is a key typed in the draft (else the stored one is used). */
  test(svc: ServiceDraft, key: string): Promise<TestResult>
  models(svc: ServiceDraft, key: string): Promise<{ ok: boolean; models?: string[]; error?: string; status?: number; detail?: string }>
  /** Which providers have a key stored in Windows Credential Manager (never the keys themselves). */
  keys(): Promise<Partial<Record<ProviderId, boolean>>>
  cacheStats(): Promise<{ count: number; bytes: number }>
  clearCache(): Promise<{ count: number; bytes: number }>
  openLogs(): void
  /** While true, Translate's global shortcuts are released so a new one can be typed here. */
  recordShortcut(on: boolean): Promise<void>
  /** Whether Windows would give Translate this shortcut (free, or already Translate's). */
  shortcutAvailable(accel: string): Promise<boolean>
  openLink(id: LinkId): void
}

export let bridge: SettingsBridge | null = null
export function setBridge(b: SettingsBridge) {
  bridge = b
}

/** Live engine status (the design lab shows both input methods ready). */
export const useEngine = create<EngineStatus>(() => ({ imeStates: { wetype: 'connected', mspinyin: 'connected' }, hotkeysUnavailable: [] }))
