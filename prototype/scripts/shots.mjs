// Captures review screenshots of the running prototype with the system Edge.
// Usage: node scripts/shots.mjs [filter] [--out=dir] [--scale=1]
import { chromium } from 'playwright-core'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'
import { createServer } from 'vite'

const args = process.argv.slice(2)
const filter = args.find((a) => !a.startsWith('--')) ?? ''
const outDir = resolve(args.find((a) => a.startsWith('--out='))?.slice(6) ?? '../screenshots/stage2')
const scale = Number(args.find((a) => a.startsWith('--scale='))?.slice(8) ?? 1)
const server = await createServer({ server: { port: 5321, strictPort: false, host: '127.0.0.1' }, logLevel: 'error' })
await server.listen()
const BASE = server.resolvedUrls.local[0]
mkdirSync(outDir, { recursive: true })

const shots = []
for (const theme of ['light', 'dark']) {
  shots.push({ name: `states-${theme}`, q: { theme, view: 'states', lang: 'en' }, w: 1440, h: 3900 })
  shots.push({ name: `components-${theme}`, q: { theme, view: 'components', lang: 'en' }, w: 1440, h: 1500 })
  for (const page of ['overview', 'general', 'translation', 'appearance', 'privacy', 'about'])
    shots.push({ name: `settings-${page}-${theme}`, q: { theme, view: 'settings', page, lang: 'en' }, w: 1100, h: 720, clip: '[role=dialog]' })
  shots.push({ name: `desktop-${theme}`, q: { theme, view: 'desktop', lang: 'en', scenario: 'partial' }, w: 1440, h: 860, act: 'type' })
}
for (const lang of ['zh-CN', 'ja', 'ko']) {
  shots.push({ name: `settings-overview-${lang}`, q: { theme: 'light', view: 'settings', page: 'overview', lang }, w: 1100, h: 720, clip: '[role=dialog]' })
  shots.push({ name: `settings-appearance-${lang}`, q: { theme: 'light', view: 'settings', page: 'appearance', lang }, w: 1100, h: 720, clip: '[role=dialog]' })
}
shots.push({ name: 'states-ja-target', q: { theme: 'light', view: 'states', lang: 'ja', target: 'ja' }, w: 1440, h: 3900 })
for (const theme of ['light', 'dark']) shots.push({ name: `icons-${theme}`, q: { theme, view: 'icons', lang: 'en' }, w: 1440, h: 2300 })

const browser = await chromium.launch({ channel: 'msedge' })
const ctx = await browser.newContext({ deviceScaleFactor: scale, reducedMotion: 'reduce' })
for (const s of shots) {
  if (filter && !s.name.includes(filter)) continue
  const page = await ctx.newPage()
  page.on('pageerror', (e) => console.log('PAGEERROR', s.name, e.message))
  page.on('console', (m) => m.type() === 'error' && console.log('CONSOLE', s.name, m.text().slice(0, 300)))
  await page.setViewportSize({ width: s.w, height: s.h })
  await page.goto(BASE + '?' + new URLSearchParams(s.q).toString())
  await page.evaluate(() => document.fonts.ready)
  await page.waitForTimeout(250)
  if (s.act === 'type') {
    await page.getByRole('button', { name: /for me/ }).click()
    await page.waitForTimeout(2200)
  }
  const file = `${outDir}/${s.name}${scale !== 1 ? `@${scale}x` : ''}.png`
  if (s.clip) await page.locator(s.clip).first().screenshot({ path: file, timeout: 5000 })
  else await page.screenshot({ path: file, fullPage: !!s.full })
  console.log('saved', file)
  await page.close()
}
await browser.close()
await server.close()
