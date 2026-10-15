// Captures the lead-preview placement cases on the simulated desktop and reports the chosen placement.
// Usage: node scripts/lead_shots.mjs [--out=dir]
import { chromium } from 'playwright-core'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'
import { createServer } from 'vite'

const out = resolve(process.argv.find((a) => a.startsWith('--out='))?.slice(6) ?? '../screenshots/stage2/lead-preview')
mkdirSync(out, { recursive: true })
const server = await createServer({ server: { port: 5324, strictPort: false, host: '127.0.0.1' }, logLevel: 'error' })
await server.listen()
const BASE = server.resolvedUrls.local[0]
const browser = await chromium.launch({ channel: 'msedge' })

const CASES = [
  { name: '1-normal', layout: 'middle', theme: 'light' },
  { name: '1-normal-dark', layout: 'middle', theme: 'dark', appTheme: 'Dark' },
  { name: '2-bottom-edge', layout: 'bottom', theme: 'light' },
  { name: '3-bottom-right', layout: 'corner', theme: 'light' },
  { name: '4-small-display-beside', layout: 'small', theme: 'light' },
  { name: '5-very-small-scroll', layout: 'tiny', theme: 'light' },
  { name: '6-very-small-scrolled', layout: 'tiny', theme: 'light', keys: ['Alt+PageDown'] },
  { name: '7-cramped-none', layout: 'cramped', theme: 'light' },
  { name: '8-cramped-overlay-on-request', layout: 'cramped', theme: 'light', keys: ['Alt+Backquote'] },
  { name: '9-hover-row-2', layout: 'middle', theme: 'light', hover: 2 },
  { name: '10-step-alt-down', layout: 'middle', theme: 'light', keys: ['Alt+ArrowDown', 'Alt+ArrowDown'] },
]

for (const c of CASES) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 860 } })
  page.on('pageerror', (e) => console.log('PAGEERROR', c.name, e.message))
  await page.goto(`${BASE}?theme=${c.theme}&view=desktop&lang=en&scenario=sentence&layout=${c.layout}`)
  await page.evaluate(() => document.fonts.ready)
  if (c.appTheme) await page.getByText(c.appTheme, { exact: true }).click()
  await page.getByRole('button', { name: /for me/ }).click()
  await page.waitForTimeout(3200)
  if (c.hover) {
    await page.getByRole('listbox', { name: 'Translations' }).getByRole('option').nth(c.hover - 1).hover()
    await page.waitForTimeout(400)
  }
  for (const k of c.keys ?? []) {
    await page.keyboard.press(k)
    await page.waitForTimeout(250)
  }
  const readout = (await page.locator('[data-readout]').innerText()).trim()
  await page.locator('[data-desk]').screenshot({ path: `${out}/${c.name}.png` })
  console.log(c.name.padEnd(26), readout)
  await page.close()
}
await browser.close()
await server.close()
