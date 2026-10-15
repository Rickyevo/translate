// Captures every panel state cell (both themes) for before/after sheets.
import { chromium } from 'playwright-core'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'
import { createServer } from 'vite'

const out = resolve('../screenshots/stage2/compare/after')
mkdirSync(out, { recursive: true })
const server = await createServer({ server: { port: 5323, strictPort: false, host: '127.0.0.1' }, logLevel: 'error' })
await server.listen()
const BASE = server.resolvedUrls.local[0]
const browser = await chromium.launch({ channel: 'msedge' })
const ctx = await browser.newContext({ viewport: { width: 1600, height: 2600 }, reducedMotion: 'reduce' })
for (const theme of ['light', 'dark']) {
  const page = await ctx.newPage()
  await page.goto(`${BASE}?theme=${theme}&view=states&lang=en`)
  await page.evaluate(() => document.fonts.ready)
  await page.waitForTimeout(300)
  for (const el of await page.locator(`[data-cell$="-${theme}"]`).all()) {
    const id = await el.getAttribute('data-cell')
    await el.screenshot({ path: `${out}/${id}.png` })
  }
  await page.close()
}
await browser.close()
await server.close()
console.log('done')
