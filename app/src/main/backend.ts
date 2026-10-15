/* Supervises the Python backend: spawn, JSON Lines framing, request/response, restart with backoff.
 * stdout = protocol only; stderr = diagnostics (forwarded to our log, never parsed). */
import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process'
import { EventEmitter } from 'node:events'
import { log } from './log'

export interface BackendMessage {
  v: number
  type: string
  id?: number
  [k: string]: unknown
}

export interface BackendOptions {
  python: string
  args: string[]
  cwd: string
  env?: NodeJS.ProcessEnv
}

const MAX_LINE = 1 << 20 // 1 MiB: anything longer is a framing error, not a message

export class Backend extends EventEmitter {
  private proc: ChildProcessWithoutNullStreams | null = null
  private buf = ''
  private nextId = 1
  private pending = new Map<number, { resolve: (m: BackendMessage) => void; timer: NodeJS.Timeout }>()
  private restarts: number[] = []
  private stopping = false
  pid = 0
  ready = false

  constructor(private opts: BackendOptions) {
    super()
  }

  start() {
    this.stopping = false
    const p = spawn(this.opts.python, this.opts.args, { cwd: this.opts.cwd, env: { ...process.env, PYTHONUTF8: '1', PYTHONDONTWRITEBYTECODE: '1', ...this.opts.env }, windowsHide: true })
    this.proc = p
    this.pid = p.pid ?? 0
    this.ready = false
    p.stdout.setEncoding('utf8')
    p.stdout.on('data', (chunk: string) => this.onData(chunk))
    p.stderr.setEncoding('utf8')
    p.stderr.on('data', (chunk: string) => chunk.split(/\r?\n/).filter(Boolean).forEach((l) => log.info('[py] ' + l)))
    p.on('exit', (code, signal) => this.onExit(code, signal))
    p.on('error', (e) => {
      log.error('backend spawn failed: ' + e.message)
      this.emit('status', { state: 'failed', message: e.message })
    })
  }

  private onData(chunk: string) {
    this.buf += chunk
    if (this.buf.length > MAX_LINE && !this.buf.includes('\n')) {
      log.error('backend line too long; dropping buffer')
      this.buf = ''
      return
    }
    let i: number
    while ((i = this.buf.indexOf('\n')) >= 0) {
      const line = this.buf.slice(0, i).trim()
      this.buf = this.buf.slice(i + 1)
      if (!line) continue
      let msg: BackendMessage
      try {
        msg = JSON.parse(line)
      } catch {
        log.error('unparseable backend line (' + line.length + ' chars)')
        continue
      }
      if (msg.type === 'ready') {
        this.ready = true
        this.emit('status', { state: 'ready', info: msg })
      }
      if (msg.id !== undefined && this.pending.has(msg.id)) {
        const p = this.pending.get(msg.id)!
        clearTimeout(p.timer)
        this.pending.delete(msg.id)
        p.resolve(msg)
      }
      this.emit('message', msg)
    }
  }

  private onExit(code: number | null, signal: NodeJS.Signals | null) {
    log.info(`backend exited code=${code} signal=${signal}`)
    this.proc = null
    this.ready = false
    for (const [, p] of this.pending) {
      clearTimeout(p.timer)
      p.resolve({ v: 1, type: 'error', code: 'backend_exit', message: 'The translation engine stopped' })
    }
    this.pending.clear()
    if (this.stopping) return
    // Restart with backoff; give up after 5 crashes within a minute.
    const now = Date.now()
    this.restarts = this.restarts.filter((t) => now - t < 60_000)
    this.restarts.push(now)
    if (this.restarts.length > 5) {
      this.emit('status', { state: 'failed', message: 'The translation engine keeps stopping' })
      return
    }
    const delay = Math.min(8000, 250 * 2 ** (this.restarts.length - 1))
    this.emit('status', { state: 'restarting', delay })
    setTimeout(() => !this.stopping && this.start(), delay)
  }

  send(type: string, fields: Record<string, unknown> = {}) {
    if (!this.proc) return
    this.proc.stdin.write(JSON.stringify({ v: 1, type, ...fields }) + '\n')
  }

  request(type: string, fields: Record<string, unknown> = {}, timeoutMs = 3000): Promise<BackendMessage> {
    const id = this.nextId++
    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        this.pending.delete(id)
        resolve({ v: 1, type: 'error', code: 'timeout', message: 'The translation engine did not answer' })
      }, timeoutMs)
      this.pending.set(id, { resolve, timer })
      this.send(type, { ...fields, id })
    })
  }

  async stop(): Promise<void> {
    this.stopping = true
    const p = this.proc
    if (!p) return
    const exited = new Promise<void>((r) => p.once('exit', () => r()))
    this.send('shutdown', { id: this.nextId++ })
    p.stdin.end()
    const timeout = new Promise<void>((r) => setTimeout(r, 1500))
    await Promise.race([exited, timeout])
    if (this.proc) p.kill()
  }
}
