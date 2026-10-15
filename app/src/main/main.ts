/* Translate — Electron main process.
 *
 * Resident footprint is a design constraint:
 *  - no window exists at startup; the panel window is created on the first candidate list
 *  - the lead preview is a child of the panel renderer (window.open → same renderer process)
 *  - settings is created on demand and destroyed on close (its renderer process exits)
 *  - no tray icon, no application menu, no polling timers; everything is event-driven
 */
import { app, BrowserWindow, clipboard, globalShortcut, ipcMain, Menu, nativeTheme, screen, shell, type Rectangle } from 'electron'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { createServer } from 'node:http'
import { join, resolve } from 'node:path'
import { Backend, type BackendMessage } from './backend'
import { log } from './log'
import { placePreview, type Placement, type Rect } from '../../../prototype/src/layout/placePreview'
import { DEFAULT_SETTINGS, type Settings } from '../../../prototype/src/model'
import type { CandidateList, Item, Target } from '../../../prototype/src/data/scenarios'
import type { PanelKey, PanelState, ThemeName } from '../shared/types'

/* ------------------------------------------------------------------ process setup */

const argv = process.argv
const testPort = Number(argv.find((a) => a.startsWith('--test-control='))?.split('=')[1] ?? 0)
// Test mode only: drive the real WeType adapter path with synthetic pipe bytes instead of scripted lists.
const testSource = testPort ? (argv.find((a) => a.startsWith('--test-source='))?.split('=')[1] ?? '') : ''
// Live verification: the real adapter and real input, plus a read-only state endpoint on localhost
// (generations, counts, geometry; never candidate text). Not available together with --test-control.
const observePort = testPort ? 0 : Number(argv.find((a) => a.startsWith('--observe='))?.split('=')[1] ?? 0)
const previewSeparate = argv.includes('--preview-separate') // measurement variant: own renderer for the preview
// Release the panel renderer after 3 min without typing (stage-3 decision); --keep-panel keeps it.
const keepPanel = argv.includes('--keep-panel')
const RELEASE_MS = Number(argv.find((a) => a.startsWith('--release-after-ms='))?.split('=')[1] ?? 180_000)

// Tests run against an isolated profile (never the user's config).
if (process.env.TRANSLATE_USER_DATA) app.setPath('userData', process.env.TRANSLATE_USER_DATA)

if (!app.requestSingleInstanceLock()) {
  app.quit()
} else {
  app.on('second-instance', () => openSettings()) // launching again = show settings of the running instance
}

app.setAppUserModelId('app.translate.desktop')
Menu.setApplicationMenu(null)
// Lean renderer processes: no spellchecker dictionaries, no extra Chromium services we don't use.
app.commandLine.appendSwitch('disable-features', 'SpareRendererForSitePerProcess,CalculateNativeWinOcclusion,MediaSessionService,HardwareMediaKeyHandling')
// Software compositing by default: the GPU process costs ~75 MB private and more CPU for a few
// small, mostly static windows (measured, docs/stage3-report.md). --gpu opts back in.
if (!argv.includes('--gpu')) app.disableHardwareAcceleration()

const ROOT = app.isPackaged ? process.resourcesPath : resolve(__dirname, '../..')
const RENDERER = app.isPackaged ? join(process.resourcesPath, 'app.asar', 'dist', 'renderer') : join(ROOT, 'dist', 'renderer')
const PRELOAD = join(__dirname, '../preload/preload.js')
const BACKEND_DIR = app.isPackaged ? join(process.resourcesPath, 'backend') : resolve(ROOT, '../backend')
const M = 16 // transparent margin around panel/preview content for the shadow
const toRect = (r: Rectangle): Rect => ({ x: r.x, y: r.y, w: r.width, h: r.height })
const toRectangle = (r: Rect): Rectangle => ({ x: Math.round(r.x), y: Math.round(r.y), width: Math.round(r.w), height: Math.round(r.h) })

/* ------------------------------------------------------------------ state */

let settings: Settings = loadSettings()
let draft: Settings | null = null // live-previewed settings while the settings window is open
let paused = false
let barHidden = false
let list: CandidateList | null = null
let composition = 0
let anchorDip: Rect | null = null
let canvasDip: Rect | null = null // the IME's whole window (takes mouse input over its area)
let dir: 'below' | 'above' = 'below'
let panelWin: BrowserWindow | null = null
let previewWin: BrowserWindow | null = null
let settingsWin: BrowserWindow | null = null
let panelContent = { w: 0, h: 0, ew: 0, eh: 0 }
let panelRows: { n: number; x: number; y: number; w: number; h: number }[] = []
let previewNeed = { wanted: false, requested: false, w: 360, h: 0 }
let placement: Placement | null = null
let lastPlaceKey = ''
let shortcutsOn = false
let releaseTimer: NodeJS.Timeout | null = null
// Stage 4: real candidates get placeholder translations; the footer says so until a provider is connected.
let translationMode: 'fixture' | 'simulated' | 'live' = 'fixture'
let imeState = 'starting'
let serviceState = '' // ok · noService · localOnly · offline · auth · failed (from the backend's pipeline)
let panelCreated = 0 // counts panel renderer creations (idle release → recreate)

const eff = (): Settings => ({ ...settings, ...(draft ? pickLive(draft) : {}) })
const pickLive = (s: Settings) => ({ theme: s.theme, textSize: s.textSize, density: s.density, opacity: s.opacity, offsetX: s.offsetX, offsetY: s.offsetY, showOriginal: s.showOriginal, leadMode: s.leadMode, uiLang: s.uiLang })
const theme = (): ThemeName => {
  const t = eff().theme
  return t === 'system' ? (nativeTheme.shouldUseDarkColors ? 'dark' : 'light') : t
}

function configPath() {
  const dir = app.getPath('userData')
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true })
  return join(dir, 'config.json')
}
// A key found in an older plaintext config.json is moved to Windows Credential Manager once the backend is up.
let legacyKey: { provider: string; key: string } | null = null
function loadSettings(): Settings {
  try {
    const raw = JSON.parse(readFileSync(configPath(), 'utf8'))
    if (typeof raw.apiKey === 'string' && raw.apiKey) legacyKey = { provider: raw.provider ?? 'openai', key: raw.apiKey }
    delete raw.endpoint, delete raw.model // stage ≤ 4 fields, replaced by provider/services
    return { ...DEFAULT_SETTINGS, ...raw, apiKey: '', services: { ...(raw.services ?? {}) }, shortcuts: { ...DEFAULT_SETTINGS.shortcuts, ...(raw.shortcuts ?? {}) } }
  } catch {
    return { ...DEFAULT_SETTINGS } // missing or corrupt → defaults (the file is rewritten on next save)
  }
}
/** config.json never holds a key: keys live in Windows Credential Manager (written by the backend). */
function saveSettingsFile(s: Settings) {
  writeFileSync(configPath(), JSON.stringify({ ...s, apiKey: undefined }, null, 2))
}

/* ------------------------------------------------------------------ backend */

// Release builds run the bundled, isolated Python runtime (resources/python, see scripts/bundle_python.py) and never a
// Python installed on the machine. Development runs use TRANSLATE_PYTHON or the `python` on PATH.
const BUNDLED_PYTHON = join(process.resourcesPath ?? '', 'python', 'TranslateEngine.exe')
const python = app.isPackaged && existsSync(BUNDLED_PYTHON) ? BUNDLED_PYTHON : process.env.TRANSLATE_PYTHON || 'python'
const backend = new Backend({ python, args: ['-E', '-s', '-B', '-m', 'translate_backend', ...(testPort ? ['--test'] : []), ...(testSource ? ['--source=' + testSource] : []), ...(testPort && argv.includes('--translator=live') ? ['--translator=live'] : [])], cwd: BACKEND_DIR })

backend.on('status', (s) => log.info('backend status ' + JSON.stringify(s)))
backend.on('message', (m: BackendMessage) => {
  switch (m.type) {
    case 'ready':
      translationMode = (m.translationMode as typeof translationMode) ?? 'fixture'
      if (list) endComposition() // a restarted backend numbers its lists from 1 again
      backend.send('config.set', { config: backendConfig() })
      if (paused) backend.send('pause') // a restarted backend starts unpaused
      if (legacyKey) {
        const k = legacyKey
        legacyKey = null
        void backend.request('secret.set', k).then(() => saveSettingsFile(settings))
      }
      break
    case 'status':
      if (m.ime) {
        imeState = (m.ime as { state: string }).state
        log.info('ime ' + imeState + ((m.ime as { code?: string }).code ? ' ' + (m.ime as { code?: string }).code : ''))
      }
      if (m.service) {
        serviceState = (m.service as { state: string }).state
        log.info('service ' + serviceState)
        if (list && list.banner !== banner()) (list = { ...list, banner: banner() }), pushState()
      }
      break
    case 'candidates':
      onCandidates(m)
      break
    case 'translation': {
      if (!list || m.gen !== list.gen) return // stale generation
      const items = list.items.map((it): Item => (it.n === m.n ? { ...it, state: m.state as Item['state'], translation: (m.text as string) ?? undefined, source: (m.source as Item['source']) ?? undefined, reason: (m.reason as Item['reason']) ?? undefined, prev: m.state === 'loading' ? it.prev : undefined } : it))
      list = { ...list, items }
      pushState()
      break
    }
    case 'composition.end':
      if (list && m.gen === list.gen) endComposition()
      break
    case 'insert.result':
      lastInsert = { ok: !!m.ok, error: (m.error as string) ?? null, gen: m.gen as number, n: m.n as number }
      // A stale list is replaced a few ms later anyway; saying so would only be noise.
      if (!m.ok && m.error !== 'stale') pushState({ key: INSERT_NOTICE[m.error as string] ?? 'notice.notInserted' })
      break
  }
})

const INSERT_NOTICE: Record<string, string> = { unavailable: 'unavailable', ime: 'notice.imeBusy', modifiers: 'notice.releaseKeys', denied: 'notice.denied' }
let lastInsert: { ok: boolean; error: string | null; gen: number; n: number } | null = null
const STALE_MS = 600
let staleTimer: NodeJS.Timeout | null = null

function backendConfig() {
  const s = settings
  return {
    target: s.target, count: s.count, denylist: s.denylist, localOnly: s.localOnly, localDict: s.localDict,
    provider: s.provider, services: s.services, timeout: s.timeout, jsonMode: s.jsonMode,
    dataDir: app.getPath('userData'), // the encrypted translation cache lives here
  }
}

/** Footer status for the list: the service state, or the stage-4 simulated marker in replay tests. */
function banner(): CandidateList['banner'] {
  if (translationMode === 'simulated') return 'simulated'
  const map: Record<string, CandidateList['banner']> = { localOnly: 'localOnly', offline: 'offline', auth: 'auth', failed: 'failed', noService: 'noService' }
  return map[serviceState] ?? null
}

function onCandidates(m: BackendMessage) {
  if (paused) return
  const gen = m.gen as number
  if (list && gen < list.gen) return // out of order: never go back to an older list
  const isNewList = !list || gen !== list.gen
  if (isNewList) {
    // A new list. Within one composition (pinyin edits) the panel stays up and keeps its width and
    // lead-preview state; only a new composition resets them.
    // Within a composition, a row still translating keeps showing (dimmed) what it showed for the previous
    // keystroke for ≤ STALE_MS, instead of flashing to a placeholder on every keystroke.
    const before = list
    const items = (m.items as { n: number; text: string; state: Item['state'] }[]).map((i): Item => {
      const old = before?.items[i.n - 1]
      const prev = i.state === 'loading' ? (old?.state === 'done' ? old.translation : old?.prev) : undefined
      return { n: i.n, text: i.text, state: i.state, ...(prev ? { prev } : {}) }
    })
    if (items.some((i) => i.prev)) {
      if (staleTimer) clearTimeout(staleTimer)
      staleTimer = setTimeout(() => {
        staleTimer = null
        if (list && list.gen === gen && list.items.some((i) => i.prev)) (list = { ...list, items: list.items.map(({ prev: _p, ...i }) => i) }), pushState()
      }, STALE_MS)
    }
    if (!list) composition++
    list = { gen, pinyin: m.pinyin as string, items, banner: banner() }
  } // same gen: the IME window moved; keep the items (and translations) we already have
  const a = m.anchor as Rect
  anchorDip = toRect(screen.screenToDipRect(null, { x: a.x, y: a.y, width: a.w, height: a.h }))
  const c = (a as Rect & { canvas?: Rect }).canvas
  canvasDip = c ? toRect(screen.screenToDipRect(null, { x: c.x, y: c.y, width: c.w, height: c.h })) : null
  ensurePanel()
  setShortcuts(true)
  if (isNewList) pushNow() // a keystroke: render at once; repositions need layout only
  layoutPanel() // same size as last time → the renderer won't report it again; show with the known size
}

function endComposition() {
  list = null
  composition++
  previewNeed = { ...previewNeed, wanted: false }
  hidePanel()
  setShortcuts(false)
  pushState()
}

/* ------------------------------------------------------------------ windows */

function baseWin(extra: Electron.BrowserWindowConstructorOptions = {}): Electron.BrowserWindowConstructorOptions {
  return {
    show: false,
    frame: false,
    transparent: true,
    resizable: false,
    movable: false,
    minimizable: false,
    maximizable: false,
    fullscreenable: false,
    skipTaskbar: true,
    focusable: false, // WS_EX_NOACTIVATE: clicks never take focus from the app being typed in
    alwaysOnTop: true,
    hasShadow: false,
    thickFrame: false,
    backgroundColor: '#00000000',
    webPreferences: { preload: PRELOAD, sandbox: true, contextIsolation: true, spellcheck: false, backgroundThrottling: false, devTools: !app.isPackaged },
    ...extra,
  }
}

function ensurePanel() {
  if (releaseTimer) clearTimeout(releaseTimer), (releaseTimer = null)
  if (panelWin && !panelWin.isDestroyed()) return panelWin
  const w = new BrowserWindow(baseWin({ width: 300, height: 220 }))
  panelCreated++
  w.setAlwaysOnTop(true, 'pop-up-menu')
  w.setIgnoreMouseEvents(true, { forward: true }) // margins pass clicks through; content toggles this off on hover
  // Only the lead preview may be opened from the panel; nothing else, ever.
  w.webContents.setWindowOpenHandler(({ url, frameName }) =>
    url === 'about:blank' && frameName === 'translate-preview' && !previewSeparate
      ? { action: 'allow', overrideBrowserWindowOptions: baseWin({ width: 400, height: 200 }) }
      : { action: 'deny' },
  )
  w.webContents.on('did-create-window', (child) => {
    previewWin = child
    child.setAlwaysOnTop(true, 'pop-up-menu')
    child.setIgnoreMouseEvents(true, { forward: true })
    child.on('closed', () => (previewWin = null))
    // The renderer asked for the preview before this window existed; place it now.
    lastPlaceKey = ''
    child.webContents.once('did-finish-load', () => layoutPreview())
    layoutPreview()
  })
  w.on('closed', () => {
    panelWin = null
    previewWin = null
    // A recreated renderer must report its own size before the window is shown (no blank frame).
    panelContent = { w: 0, h: 0, ew: 0, eh: 0 }
    lastPlaceKey = ''
  })
  watchRenderer(w, 'panel')
  w.loadFile(join(RENDERER, 'panel.html'), { query: { ...(previewSeparate ? { preview: 'separate' } : {}), ...(testPort || observePort ? { test: '1' } : {}) } })
  w.webContents.once('did-finish-load', () => pushState())
  panelWin = w
  return w
}

/** Renderer problems go to the diagnostic log (never message contents). */
function watchRenderer(w: BrowserWindow, name: string) {
  // Our pages never navigate; block anything that tries (links, drag-and-drop of files, injected script).
  w.webContents.on('will-navigate', (e) => e.preventDefault())
  if (name !== 'panel') w.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
  w.webContents.on('console-message', (e) => {
    if (e.level === 'error' || e.level === 'warning') log.warn(`[${name}] ${e.message.slice(0, 300)}`)
  })
  w.webContents.on('did-fail-load', (_e, code, desc) => log.error(`[${name}] load failed ${code} ${desc}`))
  w.webContents.on('render-process-gone', (_e, d) => log.error(`[${name}] renderer gone: ${d.reason}`))
}

let panelHides = 0 // visible → hidden transitions (test control: no hide/show per keystroke)
function hidePanel() {
  if (panelWin?.isVisible()) panelHides++
  panelWin?.isVisible() && panelWin.hide()
  previewWin?.isVisible() && previewWin.hide()
  placement = null
  if (!keepPanel && panelWin) {
    // Release the panel renderer after a pause in typing; it is recreated (~160 ms) on the next list.
    if (releaseTimer) clearTimeout(releaseTimer)
    releaseTimer = setTimeout(() => {
      if (!list) panelWin?.destroy()
      releaseTimer = null
    }, RELEASE_MS)
  }
}

/** Render scheduling. A new list (a keystroke) is pushed at once (pushNow). Everything else — mostly
 * translations arriving one by one — is coalesced to one push per 33 ms (two frames): a keystroke's five
 * results cause about two renders instead of five or six. Notices are sent immediately.
 * Measured on typing at 150 ms/keystroke: ≈ −3 % of a core (docs/stage4-report.md). */
let pushTimer: NodeJS.Timeout | null = null
const PUSH_MS = Number(argv.find((a) => a.startsWith('--push-ms='))?.split('=')[1] ?? 33)
function pushNow() {
  if (pushTimer) clearTimeout(pushTimer), (pushTimer = null)
  sendState()
}
type Notice = PanelState['notice']
function pushState(notice?: Notice) {
  if (notice) return sendState(notice)
  if (pushTimer) return
  pushTimer = setTimeout(() => {
    pushTimer = null
    sendState()
  }, PUSH_MS)
}
function sendState(notice?: Notice) {
  const state: PanelState = { list, settings: eff(), theme: theme(), paused, hidden: barHidden, composition, notice }
  if (panelWin && !panelWin.isDestroyed()) panelWin.webContents.send('state', state)
  if (previewSeparate && previewWin && !previewWin.isDestroyed()) previewWin.webContents.send('state', state)
}

/** Panel position: under the IME window (or above when there is no room), clamped to the work area. */
function layoutPanel() {
  if (!panelWin || !anchorDip || !list || barHidden || panelContent.w === 0) return
  const s = eff()
  const work = screen.getDisplayMatching(toRectangle(anchorDip)).workArea
  const { w, h } = panelContent
  // Default: directly under the candidate bar. "Keep the panel clickable": under (or above) the IME's whole
  // window instead, because that window takes all mouse input where it overlaps the panel.
  const avoid = clickableBox() ?? anchorDip
  let y = avoid.y + avoid.h + s.offsetY
  dir = 'below'
  if (y + h > work.y + work.height - 8) {
    y = avoid.y - s.offsetY - h
    dir = 'above'
    if (y < work.y + 8 && avoid !== anchorDip) {
      // No room clear of the IME window on either side: fall back to the bar (hotkeys still work).
      y = anchorDip.y + anchorDip.h + s.offsetY
      dir = 'below'
      if (y + h > work.y + work.height - 8) (y = anchorDip.y - s.offsetY - h), (dir = 'above')
    }
  }
  const x = Math.max(work.x + 8, Math.min(anchorDip.x + s.offsetX, work.x + work.width - w - 8))
  // The window also covers any open menu (extent), so menus are never clipped.
  // The window is sized to the panel's capacity (widest row × configured candidate count + footer), not to the current
  // content: rows appearing or translations getting longer between keystrokes then change only what is drawn inside
  // a stable, transparent, click-through window. Resizing it per keystroke showed a stale/blank frame each time
  // (the flicker while typing). It still grows for an open menu or larger text.
  const cap = panelCapacity()
  setBoundsIfChanged(panelWin, { x: Math.round(x) - M, y: Math.round(y) - M, width: Math.max(panelContent.ew, cap.w) + 2 * M, height: Math.max(panelContent.eh, cap.h) + 2 * M })
  if (!panelWin.isVisible()) panelWin.showInactive()
  layoutPreview()
}

function clickableBox(): Rect | null {
  return eff().clickable && canvasDip ? canvasDip : null
}

/** Largest the panel can be with the current settings (DIP): Panel.tsx metrics — max width 24.6 × text size; rows of
 * round(text size × 2.15 | 1.85 compact), 1 px gaps, 4 px padding top and bottom, a 1 px rule and the 24 px footer. */
function panelCapacity() {
  const s = eff()
  const rowH = Math.round(s.textSize * (s.density === 'compact' ? 1.85 : 2.15))
  const n = Math.max(1, Math.min(9, s.count))
  return { w: Math.round(s.textSize * 24.6) + 2, h: 8 + n * rowH + (n - 1) + 1 + 24 + 2 }
}

function contentRect(win: BrowserWindow): Rect {
  const b = win.getBounds()
  const isPanel = win === panelWin
  return { x: b.x + M, y: b.y + M, w: isPanel ? panelContent.w : b.width - 2 * M, h: isPanel ? panelContent.h : b.height - 2 * M }
}

/** Measurement variant: the preview as its own BrowserWindow with its own renderer process. */
function ensureSeparatePreview() {
  if (!previewSeparate || (previewWin && !previewWin.isDestroyed())) return
  const w = new BrowserWindow(baseWin({ width: 412, height: 200 }))
  w.setAlwaysOnTop(true, 'pop-up-menu')
  w.setIgnoreMouseEvents(true, { forward: true })
  watchRenderer(w, 'preview')
  w.loadFile(join(RENDERER, 'panel.html'), { query: { probe: '1' } })
  w.webContents.once('did-finish-load', () => pushState())
  w.on('closed', () => (previewWin = null))
  previewWin = w
}

function layoutPreview() {
  if (previewNeed.wanted) ensureSeparatePreview()
  if (!panelWin || !anchorDip || !previewWin) return
  if (!previewNeed.wanted || !list || barHidden) {
    if (previewWin.isVisible()) previewWin.hide()
    placement = null
    return
  }
  const panel = contentRect(panelWin)
  const work = screen.getDisplayMatching(toRectangle(anchorDip)).workArea
  const lineH = Math.round((eff().textSize + 1) * 1.45)
  // Typing band: no caret info from the simulated source, so infer it beside the IME window (DESIGN §9.1 fallback).
  const band: Rect = dir === 'below' ? { x: anchorDip.x - 100, y: anchorDip.y - 36, w: anchorDip.w + 200, h: 36 } : { x: anchorDip.x - 100, y: anchorDip.y + anchorDip.h, w: anchorDip.w + 200, h: 36 }
  placement = placePreview({
    work: { x: work.x, y: work.y, w: work.width, h: work.height },
    panel,
    avoid: [band, anchorDip, ...(clickableBox() ? [clickableBox()!] : [])],
    stack: dir,
    width: previewNeed.w,
    needH: previewNeed.h,
    minH: 30 + 2 * lineH + 16,
    requested: previewNeed.requested,
  })
  const msg = { kind: placement.kind, h: Math.round(placement.rect.h), w: Math.round(placement.rect.w), scroll: placement.scroll }
  const key = JSON.stringify(msg)
  if (key !== lastPlaceKey) {
    lastPlaceKey = key
    panelWin.webContents.send('preview:place', msg)
  }
  if (placement.kind === 'none') {
    if (previewWin.isVisible()) previewWin.hide()
    return
  }
  const r = placement.rect
  setBoundsIfChanged(previewWin, { x: Math.round(r.x) - M, y: Math.round(r.y) - M, width: Math.round(r.w) + 2 * M, height: Math.round(r.h) + 2 * M })
  if (!previewWin.isVisible()) previewWin.showInactive()
}

let windowResizes = 0 // test control: size changes of the panel/preview windows (each can show a stale frame)
function setBoundsIfChanged(win: BrowserWindow, b: Rectangle) {
  const c = win.getBounds()
  if (c.width !== b.width || c.height !== b.height) windowResizes++
  if (c.x !== b.x || c.y !== b.y || c.width !== b.width || c.height !== b.height) win.setBounds(b)
}

function openSettings(page?: string, inactive = false) {
  if (settingsWin && !settingsWin.isDestroyed()) {
    if (settingsWin.isMinimized()) settingsWin.restore()
    settingsWin.show()
    settingsWin.focus()
    return
  }
  const w = new BrowserWindow({
    width: 860,
    height: 620,
    show: false,
    frame: false,
    resizable: false,
    maximizable: false,
    fullscreenable: false,
    title: 'Translate',
    backgroundColor: theme() === 'dark' ? '#1d2127' : '#f4f6f8',
    icon: join(ROOT, 'build', 'icon.ico'),
    webPreferences: { preload: PRELOAD, sandbox: true, contextIsolation: true, spellcheck: false, devTools: !app.isPackaged },
  })
  watchRenderer(w, 'settings')
  w.loadFile(join(RENDERER, 'settings.html'), { query: page ? { page } : {} })
  w.once('ready-to-show', () => (inactive ? w.showInactive() : w.show()))
  w.on('closed', () => {
    // Closing without saving = Cancel: live-previewed values revert on the panel.
    settingsWin = null
    if (draft) {
      draft = null
      pushState()
      layoutPanel()
    }
  })
  settingsWin = w
}

/* ------------------------------------------------------------------ shortcuts */

function setShortcuts(on: boolean) {
  if (on === shortcutsOn) return
  shortcutsOn = on
  const reg = (acc: string, fn: () => void) => {
    if (!globalShortcut.register(acc, fn)) log.warn('shortcut unavailable: ' + acc)
  }
  const keys = ['1', '2', '3', '4', '5', '6', '7', '8', '9']
  if (on) {
    keys.forEach((k) => {
      reg('Alt+' + k, () => list && insert(list.gen, Number(k)))
      reg('Alt+Shift+' + k, () => list && copy(list.gen, Number(k)))
    })
    reg('Alt+0', toggleHidden)
    const key = (k: PanelKey) => panelWin?.webContents.send('key', k)
    reg('Alt+`', () => key({ action: 'togglePreview' }))
    reg('Alt+Down', () => key({ action: 'step', d: 1 }))
    reg('Alt+Up', () => key({ action: 'step', d: -1 }))
    reg('Alt+PageDown', () => key({ action: 'scroll', d: 1 }))
    reg('Alt+PageUp', () => key({ action: 'scroll', d: -1 }))
  } else {
    keys.forEach((k) => {
      globalShortcut.unregister('Alt+' + k)
      globalShortcut.unregister('Alt+Shift+' + k)
    })
    ;['Alt+0', 'Alt+`', 'Alt+Down', 'Alt+Up', 'Alt+PageDown', 'Alt+PageUp'].forEach((a) => globalShortcut.unregister(a))
  }
}

function toggleHidden() {
  barHidden = !barHidden
  if (barHidden) hidePanel()
  pushState()
  layoutPanel()
}

function registerGlobal() {
  globalShortcut.register(settings.shortcuts.pause, () => setPaused(!paused))
  globalShortcut.register(settings.shortcuts.settings, () => openSettings())
}

function setPaused(p: boolean) {
  paused = p
  backend.send(p ? 'pause' : 'resume')
  if (p) endComposition()
  settingsWin?.webContents.send('paused', p)
}

/* ------------------------------------------------------------------ actions */

function insert(gen: number, n: number) {
  backend.send('insert', { gen, n })
}
function copy(gen: number, n: number) {
  const it = list && list.gen === gen ? list.items[n - 1] : undefined
  if (it?.state === 'done' && it.translation) {
    clipboard.writeText(it.translation)
    pushState({ key: 'notice.copiedText', text: it.translation })
  } else pushState({ key: 'unavailable' })
}

/* ------------------------------------------------------------------ IPC */

ipcMain.on('panel:size', (_e, w: number, h: number, ew: number, eh: number) => {
  const next = { w: Math.ceil(w), h: Math.ceil(h), ew: Math.ceil(Math.max(w, ew)), eh: Math.ceil(Math.max(h, eh)) }
  if (next.w === panelContent.w && next.h === panelContent.h && next.ew === panelContent.ew && next.eh === panelContent.eh) return
  panelContent = next
  layoutPanel()
})
ipcMain.on('panel:rows', (_e, rows) => (panelRows = rows))
const mouseLog: string[] = [] // test control: pass-through transitions (which:inside), newest last
ipcMain.on('mouse', (_e, which: 'panel' | 'preview', inside: boolean) => {
  if (testPort) mouseLog.push(`${which}:${inside ? 'in' : 'out'}`), mouseLog.length > 50 && mouseLog.shift()
  const w = which === 'panel' ? panelWin : previewWin
  w?.setIgnoreMouseEvents(!inside, { forward: true })
})
ipcMain.on('panel:insert', (_e, gen: number, n: number) => insert(gen, n))
ipcMain.on('panel:copy', (_e, gen: number, n: number) => copy(gen, n))
ipcMain.on('panel:retry', (_e, gen: number, n: number) => backend.send('retry', { gen, n }))
ipcMain.on('panel:target', (_e, t: Target) => {
  settings = { ...settings, target: t }
  saveSettingsFile(settings)
  backend.send('config.set', { config: backendConfig() })
  pushState()
})
ipcMain.on('panel:menu', (_e, a: string) => {
  if (a === 'pause') setPaused(!paused)
  if (a === 'hide') (barHidden = true), hidePanel(), pushState()
  if (a === 'settings') openSettings()
  if (a === 'quit') app.quit()
})
ipcMain.on('preview:need', (_e, need) => {
  previewNeed = need
  layoutPreview()
})
ipcMain.handle('settings:get', () => ({ saved: { ...settings, apiKey: '' }, theme: theme(), paused, version: app.getVersion() }))
ipcMain.handle('settings:save', (_e, s: Settings) => saveSettings(s))
async function saveSettings(s: Settings) {
  // A newly typed key goes to the backend, which stores it in Windows Credential Manager; it is not kept here.
  if (s.apiKey?.trim()) await backend.request('secret.set', { provider: s.provider, key: s.apiKey.trim() })
  settings = { ...s, apiKey: '' }
  draft = null
  saveSettingsFile(settings)
  backend.send('config.set', { config: backendConfig() })
  pushState()
  layoutPanel()
}
// Settings window → backend (real service calls with the draft; keys typed in the draft are used for the call only).
ipcMain.handle('svc:test', (_e, service, key: string) => backend.request('service.test', { service, key }, 60_000))
ipcMain.handle('svc:models', (_e, service, key: string) => backend.request('service.models', { service, key }, 60_000))
ipcMain.handle('svc:keys', async () => ((await backend.request('secret.status')).keys as Record<string, boolean>) ?? {})
ipcMain.handle('cache:stats', () => backend.request('cache.stats'))
ipcMain.handle('cache:clear', () => backend.request('cache.clear'))
ipcMain.handle('status:get', () => ({ ime: imeState, service: serviceState }))
ipcMain.on('logs:open', () => void shell.openPath(join(app.getPath('userData'), 'logs')))
ipcMain.on('settings:draft', (_e, s: Settings) => {
  draft = s
  pushState()
  layoutPanel()
})
ipcMain.on('paused', (_e, p: boolean) => setPaused(p))
ipcMain.on('window', (e, a: 'close' | 'minimize') => {
  const w = BrowserWindow.fromWebContents(e.sender)
  if (a === 'close') w?.close()
  else w?.minimize()
})
ipcMain.on('quit', () => app.quit())

nativeTheme.on('updated', () => {
  pushState()
  settingsWin?.webContents.send('theme', theme())
})

/* ------------------------------------------------------------------ lifecycle */

app.whenReady().then(() => {
  backend.start()
  registerGlobal()
  if (testPort) startTestControl(testPort)
  else if (observePort) startTestControl(observePort, true)
  log.info(`started v${app.getVersion()} packaged=${app.isPackaged} keepPanel=${keepPanel} previewSeparate=${previewSeparate}`)
})
app.on('window-all-closed', () => {
  /* resident: closing windows never quits */
})
let quitting = false
app.on('before-quit', (e) => {
  if (quitting) return
  e.preventDefault()
  quitting = true
  globalShortcut.unregisterAll()
  backend.stop().finally(() => app.exit(0))
})

/* ------------------------------------------------------------------ test control (only with --test-control=PORT) */

function startTestControl(port: number, readOnly = false) {
  const json = (res: import('node:http').ServerResponse, body: unknown) => {
    res.writeHead(200, { 'content-type': 'application/json' })
    res.end(JSON.stringify(body))
  }
  createServer((req, res) => {
    let body = ''
    req.on('data', (c) => (body += c))
    req.on('end', async () => {
      const q = body ? JSON.parse(body) : {}
      const url = req.url ?? ''
      if (readOnly && !['/state', '/pids', '/quit'].includes(url)) return res.writeHead(403).end()
      if (url === '/state') {
        const toPhys = (r: Rectangle) => screen.dipToScreenRect(null, r)
        const pb = panelWin && !panelWin.isDestroyed() ? panelWin.getBounds() : null
        const rows = pb ? panelRows.map((r) => ({ n: r.n, dip: { x: pb.x + r.x, y: pb.y + r.y, width: r.w, height: r.h }, phys: toPhys({ x: Math.round(pb.x + r.x), y: Math.round(pb.y + r.y), width: Math.round(r.w), height: Math.round(r.h) }) })) : []
        const prb = previewWin && !previewWin.isDestroyed() && previewWin.isVisible() ? previewWin.getBounds() : null
        return json(res, {
          panel: pb ? { visible: panelWin!.isVisible(), bounds: pb, content: contentRect(panelWin!), phys: toPhys(pb) } : null,
          rows,
          preview: prb ? { kind: placement?.kind, bounds: prb, phys: toPhys(prb), contentPhys: toPhys({ x: prb.x + M, y: prb.y + M, width: prb.width - 2 * M, height: prb.height - 2 * M }) } : null,
          settingsOpen: !!settingsWin,
          // Generations, states and counts only: candidate text never leaves the process via this endpoint.
          list: list ? { gen: list.gen, states: list.items.map((i) => i.state), count: list.items.length, banner: list.banner, sim: list.items.map((i) => i.source === 'sim') } : null,
          composition,
          hidden: barHidden,
          panelExists: !!panelWin && !panelWin.isDestroyed(),
          panelCreated,
          panelHides,
          windowResizes,
          anchorDip,
          canvasDip,
          imeState,
          translationMode,
          lastInsert,
          serviceState,
          mouseLog: mouseLog.slice(-12),
          previewExists: !!previewWin && !previewWin.isDestroyed(),
          previewWanted: previewNeed.wanted,
          hwnd: {
            panel: panelWin && !panelWin.isDestroyed() ? Number(panelWin.getNativeWindowHandle().readBigUInt64LE()) : 0,
            preview: previewWin && !previewWin.isDestroyed() ? Number(previewWin.getNativeWindowHandle().readBigUInt64LE()) : 0,
          },
          sources: list ? list.items.map((i) => i.source ?? null) : null,
          reasons: list ? list.items.map((i) => i.reason ?? null) : null,
          stale: list ? list.items.map((i) => i.state === 'loading' && !!i.prev) : null,
          backendPid: backend.pid,
          mainPid: process.pid,
          paused,
        })
      }
      if (url === '/compose') return json(res, await backend.request('debug.compose', q))
      if (url === '/end') return json(res, await backend.request('debug.end'))
      if (url === '/foreground') return json(res, await backend.request('debug.foreground'))
      if (url === '/settings/open') return openSettings(q.page, !!q.inactive), json(res, { ok: true })
      if (url === '/typing') return json(res, await backend.request('debug.typing', q))
      if (url === '/pids') return json(res, { main: process.pid, backend: backend.pid, panel: panelWin?.webContents.getOSProcessId() ?? 0, preview: previewWin?.webContents.getOSProcessId() ?? 0, settings: settingsWin?.webContents.getOSProcessId() ?? 0 })
      if (url === '/settings/close') return settingsWin?.close(), json(res, { ok: true })
      if (url === '/key') return panelWin?.webContents.send('key', q), json(res, { ok: true })
      if (url === '/quit') return json(res, { ok: true }), app.quit()
      if (url === '/wetype') return json(res, await backend.request('debug.wetype.' + q.t, q.f ?? {}))
      if (url === '/input') return json(res, await backend.request('debug.input', q))
      if (url === '/insert') return json(res, await backend.request('insert', { gen: q.gen ?? list?.gen, n: q.n ?? 1 }))
      if (url === '/toggle-hidden') return toggleHidden(), json(res, { ok: true, hidden: barHidden })
      if (url === '/pause') return setPaused(!!q.paused), json(res, { ok: true, paused })
      // Same path as the settings window's Save (key → vault, config.json without it).
      if (url === '/settings/save') return await saveSettings({ ...settings, ...q }), json(res, { ok: true })
      if (url === '/retry') return backend.send('retry', { gen: q.gen ?? list?.gen, n: q.n ?? 1 }), json(res, { ok: true })
      if (url === '/svc-test') return json(res, await backend.request('service.test', q, 60_000))
      if (url === '/svc-models') return json(res, await backend.request('service.models', q, 60_000))
      if (url === '/cache') return json(res, await backend.request(q.clear ? 'cache.clear' : 'cache.stats'))
      // Replay source only (synthetic candidates): translations, for scoring accuracy against a real service.
      if (url === '/translations' && testSource === 'wetype-replay') return json(res, list ? list.items.map((i) => ({ n: i.n, text: i.text, translation: i.translation ?? null, state: i.state, source: i.source ?? null, reason: i.reason ?? null })) : null)
      if (url === '/settings/set') return (settings = { ...settings, ...q }), saveSettingsFile(settings), pushState(), layoutPanel(), json(res, { ok: true })
      res.writeHead(404).end()
    })
  }).listen(port, '127.0.0.1')
  log.info((readOnly ? 'observe' : 'test control') + ' on 127.0.0.1:' + port)
}
