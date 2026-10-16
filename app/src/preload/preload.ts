/* The only bridge between renderers and main. Exposes a narrow, typed API; no Node in renderers.
 * Secrets (API keys) never pass through here except when the settings page saves them. */
import { contextBridge, ipcRenderer } from 'electron'
import type { TranslateApi } from '../shared/types'

const api: TranslateApi = {
  onState: (cb) => void ipcRenderer.on('state', (_e, s) => cb(s)),
  onKey: (cb) => void ipcRenderer.on('key', (_e, k) => cb(k)),
  onPreviewPlacement: (cb) => void ipcRenderer.on('preview:place', (_e, p) => cb(p)),
  panelSize: (w, h, ew, eh) => ipcRenderer.send('panel:size', w, h, ew, eh),
  panelRows: (rows) => ipcRenderer.send('panel:rows', rows),
  mouseInside: (win, inside) => ipcRenderer.send('mouse', win, inside),
  insert: (gen, n) => ipcRenderer.send('panel:insert', gen, n),
  copy: (gen, n) => ipcRenderer.send('panel:copy', gen, n),
  retry: (gen, n) => ipcRenderer.send('panel:retry', gen, n),
  previewNeed: (need) => ipcRenderer.send('preview:need', need),
  getSettings: () => ipcRenderer.invoke('settings:get'),
  saveSettings: (s) => ipcRenderer.invoke('settings:save', s),
  draftSettings: (s) => ipcRenderer.send('settings:draft', s),
  setPaused: (p) => ipcRenderer.send('paused', p),
  windowAction: (a) => ipcRenderer.send('window', a),
  quit: () => ipcRenderer.send('quit'),
  onTheme: (cb) => void ipcRenderer.on('theme', (_e, t) => cb(t)),
  onPaused: (cb) => void ipcRenderer.on('paused', (_e, p) => cb(p)),
  onTranslatedOnce: (cb) => void ipcRenderer.on('translated-once', () => cb()),
  svcTest: (service, key) => ipcRenderer.invoke('svc:test', service, key),
  svcModels: (service, key) => ipcRenderer.invoke('svc:models', service, key),
  svcKeys: () => ipcRenderer.invoke('svc:keys'),
  cacheStats: () => ipcRenderer.invoke('cache:stats'),
  cacheClear: () => ipcRenderer.invoke('cache:clear'),
  statusGet: () => ipcRenderer.invoke('status:get'),
  openLogs: () => ipcRenderer.send('logs:open'),
}

contextBridge.exposeInMainWorld('translate', api)
