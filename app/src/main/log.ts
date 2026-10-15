/* Size-capped diagnostic log in %APPDATA%/Translate/logs. No candidate text is ever written here. */
import { app } from 'electron'
import { appendFileSync, existsSync, mkdirSync, renameSync, statSync } from 'node:fs'
import { join } from 'node:path'

const MAX = 1024 * 1024 // 1 MiB per file, one rotation (≤ 2 MiB total)
let file = ''

function path() {
  if (!file) {
    const dir = join(app.getPath('userData'), 'logs')
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true })
    file = join(dir, 'translate.log')
  }
  return file
}

function write(level: string, msg: string) {
  const line = `${new Date().toISOString()} ${level} ${msg}\n`
  try {
    const p = path()
    if (existsSync(p) && statSync(p).size > MAX) renameSync(p, p + '.1')
    appendFileSync(p, line)
  } catch {
    /* logging must never crash the app */
  }
  if (!app.isPackaged) process.stdout.write(line)
}

export const log = {
  info: (m: string) => write('I', m),
  warn: (m: string) => write('W', m),
  error: (m: string) => write('E', m),
}
