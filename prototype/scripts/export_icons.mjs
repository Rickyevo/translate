// Exports every icon concept as SVG + PNG at Windows sizes (app plate and tray glyph).
// Output: ../assets/icons/concepts/<id>/
import { chromium } from 'playwright-core'
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { createServer } from 'vite'

const server = await createServer({ server: { middlewareMode: true }, logLevel: 'error' })
const { CONCEPTS, iconSvg, glyphSvg } = await server.ssrLoadModule('/src/icons/concepts.ts')
const browser = await chromium.launch({ channel: 'msedge' })
const page = await browser.newPage({ deviceScaleFactor: 1 })
const APP = [16, 20, 24, 32, 40, 48, 64, 96, 256]
const TRAY = [16, 20, 24, 32]
const png = async (svg, size, file, bg = 'transparent') => {
  await page.setContent(`<html><body style="margin:0;background:${bg}"><div id="i" style="width:${size}px;height:${size}px;display:flex">${svg}</div></body></html>`)
  await page.locator('#i').screenshot({ path: file, omitBackground: bg === 'transparent' })
}
for (const c of CONCEPTS) {
  const dir = resolve(`../assets/icons/concepts/${c.id}`)
  mkdirSync(dir, { recursive: true })
  writeFileSync(`${dir}/app.svg`, iconSvg(c.id, 256))
  writeFileSync(`${dir}/app-small.svg`, iconSvg(c.id, 16))
  writeFileSync(`${dir}/glyph.svg`, glyphSvg(c.id, 16))
  for (const s of APP) await png(iconSvg(c.id, s), s, `${dir}/app-${s}.png`)
  for (const s of TRAY) {
    await png(glyphSvg(c.id, s, '#ffffff'), s, `${dir}/tray-${s}-white.png`)
    await png(glyphSvg(c.id, s, '#1b1b1b'), s, `${dir}/tray-${s}-black.png`)
  }
  console.log('exported', c.id)
}
await browser.close()
await server.close()
