// window.translate for the panel and Settings pages — the same API the Electron preload exposed
// (app/src/shared/types.ts), over Tauri IPC: page → host through one "ipc" command, host → page through
// window.__translateEmit(channel, payload). Runs before the page's own scripts.
;(() => {
  if (window.translate || !window.__TAURI_INTERNALS__) return
  const listeners = {}
  Object.defineProperty(window, '__translateEmit', {
    value: (ch, payload) => {
      for (const cb of listeners[ch] || []) {
        try {
          cb(payload)
        } catch (e) {
          console.error(e)
        }
      }
    },
  })
  const on = (ch) => (cb) => void (listeners[ch] || (listeners[ch] = [])).push(cb)
  const invoke = (ch, args) => window.__TAURI_INTERNALS__.invoke('ipc', { ch, args: args || [] })
  const send = (ch, ...args) => void invoke(ch, args).catch(() => {})
  const api = {
    // panel
    onState: on('state'),
    onKey: on('key'),
    onPreviewPlacement: on('preview:place'),
    panelSize: (w, h, ew, eh) => send('panel:size', w, h, ew, eh),
    panelRows: (rows) => send('panel:rows', rows),
    mouseInside: (win, inside) => send('mouse', win, inside),
    insert: (gen, n) => send('panel:insert', gen, n),
    copy: (gen, n) => send('panel:copy', gen, n),
    retry: (gen, n) => send('panel:retry', gen, n),
    previewNeed: (need) => send('preview:need', need),
    // settings
    getSettings: () => invoke('settings:get'),
    saveSettings: (s) => invoke('settings:save', [s]),
    draftSettings: (s) => send('settings:draft', s),
    setPaused: (p) => send('paused', p),
    windowAction: (a) => send('window', a),
    quit: () => send('quit'),
    onTheme: on('theme'),
    onPaused: on('paused'),
    svcTest: (service, key) => invoke('svc:test', [service, key]),
    svcModels: (service, key) => invoke('svc:models', [service, key]),
    svcKeys: () => invoke('svc:keys'),
    cacheStats: () => invoke('cache:stats'),
    cacheClear: () => invoke('cache:clear'),
    statusGet: () => invoke('status:get'),
    openLogs: () => send('logs:open'),
  }
  Object.defineProperty(window, 'translate', { value: Object.freeze(api) })

  // Title-bar dragging: elements styled -webkit-app-region: drag (Tailwind class [-webkit-app-region:drag]).
  const region = (el) => {
    const cls = typeof el.className === 'string' ? el.className : ''
    if (cls.includes('app-region:no-drag')) return 'no-drag'
    if (cls.includes('app-region:drag')) return 'drag'
    const cs = getComputedStyle(el)
    return cs.getPropertyValue('-webkit-app-region') || cs.getPropertyValue('app-region') || ''
  }
  addEventListener(
    'mousedown',
    (e) => {
      if (e.button !== 0) return
      for (let el = e.target; el && el.nodeType === 1; el = el.parentElement) {
        const r = region(el)
        if (r === 'no-drag') return
        if (r === 'drag') {
          e.preventDefault()
          send('window', 'drag')
          return
        }
      }
    },
    true,
  )
  // Our pages never navigate or open files.
  addEventListener('dragover', (e) => e.preventDefault())
  addEventListener('drop', (e) => e.preventDefault())
  // Script errors → the host's diagnostic log (message only).
  addEventListener('error', (e) => send('log', String(e.message || '').slice(0, 300)))
  addEventListener('unhandledrejection', (e) => send('log', String(e.reason || '').slice(0, 300)))
  // The page can receive state now; its viewport size lets the host correct the window's size before showing it.
  addEventListener('DOMContentLoaded', () => send('hello', innerWidth, innerHeight))
  addEventListener('resize', () => send('viewport', innerWidth, innerHeight))
})()
