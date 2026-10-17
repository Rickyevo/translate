/* Customizable global shortcuts: reading one from a key press and checking it before it is saved.
 * Accelerators are written "Ctrl+Alt+Shift+Key" — the form the host registers (app/src-tauri/src/system.rs
 * parse_accel). '' means the shortcut is off. */
import { DEFAULT_SETTINGS, type Settings } from '../model'

export type ShortcutId = keyof Settings['shortcuts']
export const SHORTCUT_IDS: ShortcutId[] = ['pause', 'settings', 'toggleBar']
export const DEFAULT_SHORTCUTS = DEFAULT_SETTINGS.shortcuts

/** Keys of the panel that can't be changed (registered while the panel shows). */
export const PANEL_KEYS = [
  ...Array.from({ length: 9 }, (_, i) => `Alt+${i + 1}`),
  ...Array.from({ length: 9 }, (_, i) => `Alt+Shift+${i + 1}`),
  'Alt+`',
  'Alt+Up',
  'Alt+Down',
  'Alt+PageUp',
  'Alt+PageDown',
]
/** Combinations Windows keeps for itself. */
const SYSTEM_KEYS = ['Alt+Tab', 'Alt+F4', 'Alt+Space', 'Alt+Escape', 'Ctrl+Escape', 'Ctrl+Alt+Delete', 'Ctrl+Shift+Escape', 'Alt+Shift+Tab']

const KEY_OF_CODE: Record<string, string> = { Backquote: '`', ArrowUp: 'Up', ArrowDown: 'Down', ArrowLeft: 'Left', ArrowRight: 'Right', PageUp: 'PageUp', PageDown: 'PageDown', Space: 'Space' }

/** The key part of an accelerator for a KeyboardEvent.code, or null for keys a shortcut can't use. */
function keyOf(code: string): string | null {
  if (/^Key[A-Z]$/.test(code)) return code.slice(3)
  if (/^Digit\d$/.test(code)) return code.slice(5)
  if (/^F([1-9]|1\d|2[0-4])$/.test(code)) return code
  return KEY_OF_CODE[code] ?? null
}

export type Captured = { accel: string } | { pending: true } | { invalid: 'key' }

/** A key press while recording: modifiers alone keep waiting; a key gives the accelerator (by physical key, so it
 *  doesn't depend on the keyboard layout). */
export function capture(e: Pick<KeyboardEvent, 'code' | 'ctrlKey' | 'altKey' | 'shiftKey'>): Captured {
  if (/^(Control|Alt|Shift|Meta|OS)(Left|Right)?$/.test(e.code)) return { pending: true }
  const key = keyOf(e.code)
  if (!key) return { invalid: 'key' }
  const mods = [e.ctrlKey && 'Ctrl', e.altKey && 'Alt', e.shiftKey && 'Shift'].filter(Boolean) as string[]
  return { accel: [...mods, key].join('+') }
}

export type Problem = { kind: 'modifier' | 'system' | 'panel' } | { kind: 'duplicate'; other: ShortcutId }

/** Why an accelerator can't be used for `id` (before asking Windows whether it's free), or null. */
export function problem(accel: string, id: ShortcutId, all: Settings['shortcuts']): Problem | null {
  const has = (m: string) => accel.split('+').includes(m)
  // Ctrl+letter or Shift+letter alone would take a common key away from every app.
  if (!has('Alt') && !(has('Ctrl') && has('Shift'))) return { kind: 'modifier' }
  const same = (a: string) => a.toLowerCase() === accel.toLowerCase()
  if (SYSTEM_KEYS.some(same)) return { kind: 'system' }
  if (PANEL_KEYS.some(same)) return { kind: 'panel' }
  const other = SHORTCUT_IDS.find((o) => o !== id && same(all[o]))
  return other ? { kind: 'duplicate', other } : null
}
