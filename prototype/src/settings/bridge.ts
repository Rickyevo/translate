/* Settings ↔ app bridge. The Electron settings window installs real implementations (main process → backend);
 * the design prototype leaves it null and the pages fall back to their simulated behaviour. */
import type { ProviderId, serviceOf } from '../model'

export type ServiceDraft = ReturnType<typeof serviceOf> & { jsonMode?: boolean }
export type TestResult = { ok: true; ms: number } | { ok: false; error: string; status?: number; detail?: string }

export interface SettingsBridge {
  /** Real request with the draft settings; `key` is a key typed in the draft (else the stored one is used). */
  test(svc: ServiceDraft, key: string): Promise<TestResult>
  models(svc: ServiceDraft, key: string): Promise<{ ok: boolean; models?: string[]; error?: string; status?: number; detail?: string }>
  /** Which providers have a key stored in Windows Credential Manager (never the keys themselves). */
  keys(): Promise<Partial<Record<ProviderId, boolean>>>
  cacheStats(): Promise<{ count: number; bytes: number }>
  clearCache(): Promise<{ count: number; bytes: number }>
  openLogs(): void
  /** Engine status: the input method's state and which one (wetype | mspinyin) Translate is following. */
  status(): Promise<{ ime: string; service: string; imeName?: string; imeStates?: Record<string, string> }>
}

export let bridge: SettingsBridge | null = null
export function setBridge(b: SettingsBridge) {
  bridge = b
}
