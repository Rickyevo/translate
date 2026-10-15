// End-to-end interaction checks on the prototype (simulated desktop) in system Edge.
// Usage: node scripts/interact.mjs  → prints results, saves moment screenshots + results.json.
import { chromium } from 'playwright-core'
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { createServer } from 'vite'

const out = resolve(process.argv[2] ?? '../screenshots/stage2/interaction')
mkdirSync(out, { recursive: true })
const server = await createServer({ server: { port: 5322, strictPort: false, host: '127.0.0.1' }, logLevel: 'error' })
await server.listen()
const BASE = server.resolvedUrls.local[0]
const browser = await chromium.launch({ channel: 'msedge' })
const results = []
const check = (name, ok, detail = '') => {
  results.push({ name, ok, detail })
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ' — ' + detail : ''}`)
}

const ctx = await browser.newContext({ viewport: { width: 1440, height: 860 }, permissions: ['clipboard-read', 'clipboard-write'] })
const page = await ctx.newPage()
const errors = []
page.on('pageerror', (e) => errors.push(e.message))
await page.goto(`${BASE}?theme=light&view=desktop&lang=en&scenario=short`)
await page.evaluate(() => document.fonts.ready)
const field = page.getByRole('textbox', { name: 'Message' })
const panel = page.getByRole('listbox', { name: 'Translations' })
const rows = panel.getByRole('option')
const fieldText = () => field.innerText()
const focusedIsField = () => page.evaluate(() => document.activeElement?.getAttribute('aria-label') === 'Message')
const width = async () => Math.round((await panel.boundingBox())?.width ?? 0)
const around = async () => {
  const b = await panel.boundingBox()
  return { x: Math.max(0, b.x - 40), y: Math.max(0, b.y - 90), width: b.width + 340, height: b.height + 150 }
}
const scenario = async (name) => {
  await page.getByRole('button', { name, exact: true }).click()
  await page.waitForTimeout(2600)
}

// 1. Typing → translations in candidate order; panel fits short content.
await field.click()
await page.keyboard.type('shijian', { delay: 40 })
await page.waitForTimeout(1200)
const opts = await rows.allInnerTexts()
check('Translations listed in candidate order', /time/.test(opts[0]) && /event/.test(opts[1]) && /practice/.test(opts[2]), opts.map((o) => o.replace(/\s+/g, ' ')).join(' | '))
const wShort = await width()
check('Panel fits short content (≤ 240 px, was 300)', wShort <= 240, `${wShort} px`)

// 2. Peek only when it adds something.
await rows.nth(1).hover()
await page.waitForTimeout(600)
const noPeek = !(await page.getByText('Translation service', { exact: true }).isVisible().catch(() => false))
check('No peek on a fully visible translation', noPeek)

// 3. Click inserts, focus stays in the field.
await rows.nth(1).click()
await page.waitForTimeout(400)
check('Click inserts translation', (await fieldText()).includes('event'), JSON.stringify(await fieldText()))
check('Field keeps focus after clicking the panel', await focusedIsField())
check('Composition cleared after insert', (await panel.count()) === 0)

// 4. Alt+N, Alt held.
await page.keyboard.type('shijian', { delay: 30 })
await page.waitForTimeout(1200)
await page.keyboard.down('Alt')
await page.waitForTimeout(150)
await page.screenshot({ path: `${out}/alt-held.png`, clip: await around() })
await page.keyboard.press('Digit3')
await page.keyboard.up('Alt')
await page.waitForTimeout(400)
check('Alt+3 inserts translation #3', (await fieldText()).endsWith('practice'), JSON.stringify(await fieldText()))

// 5. Alt+Shift+N copies without inserting.
await page.keyboard.type('shijian', { delay: 30 })
await page.waitForTimeout(1200)
const before5 = await fieldText()
await page.keyboard.press('Alt+Shift+Digit2')
await page.waitForTimeout(200)
const copiedShown = await page.getByText('Copied — event').isVisible().catch(() => false)
const clip = await page.evaluate(() => navigator.clipboard.readText()).catch(() => '')
await page.screenshot({ path: `${out}/copied.png`, clip: await around() })
check('Alt+Shift+2 copies #2, field unchanged', copiedShown && (await fieldText()) === before5 && clip === 'event', `clipboard=${JSON.stringify(clip)}`)

// 6. Right-click menu: Insert / Copy; insert keeps focus.
await rows.nth(2).click({ button: 'right' })
await page.waitForTimeout(250)
const menuOk = (await page.getByRole('menuitem', { name: /Copy/ }).isVisible()) && (await page.getByRole('menuitem', { name: /Insert/ }).isVisible())
await page.screenshot({ path: `${out}/context-menu.png`, clip: await around() })
await page.getByRole('menuitem', { name: /Insert/ }).click()
await page.waitForTimeout(400)
check('Right-click menu offers Insert + Copy; Insert works', menuOk && (await fieldText()).endsWith('practice'), JSON.stringify(await fieldText()))
check('Field keeps focus after the context menu', await focusedIsField())

// 7. Width only grows within one composition, resets on the next.
await scenario('Long')
const wLong = await width()
await page.screenshot({ path: `${out}/long.png`, clip: await around() })
await scenario('Short')
const wBack = await width()
check('Long phrases widen the panel, capped at 320 px', wLong > wShort && wLong <= 320, `${wShort} → ${wLong} px`)
check('Width does not shrink back within the same composition', wBack >= wLong, `${wLong} → ${wBack} px`)
await page.keyboard.press('Escape')
await page.keyboard.type('shi', { delay: 30 })
await page.waitForTimeout(1200)
const wNew = await width()
check('Next composition starts compact again', wNew <= 240, `${wNew} px`)

// 8. Peek on a truncated row.
await scenario('Long')
await rows.nth(0).hover()
await page.waitForTimeout(600)
const peekShown = (await page.getByText("Let's discuss this question again tomorrow").count()) >= 2 // row (clipped) + peek
await page.screenshot({ path: `${out}/peek-truncated.png`, clip: await around() })
check('Truncated row shows full text on hover', peekShown)
await page.mouse.move(10, 10)

// 8b. Lead preview — automatic for a cut-off #1, stable rows, passive body, keys, focus.
const preview = page.locator('[data-preview]')
await page.mouse.move(10, 10)
await page.keyboard.press('Escape') // new composition (the preview is sticky within one)
await scenario('Short')
check('No lead preview when #1 fits', (await preview.count()) === 0)
await page.keyboard.press('Escape')
await scenario('Sentence')
const row2Before = (await rows.nth(1).boundingBox()).y
await page.waitForTimeout(400)
const kind = await preview.getAttribute('data-preview').catch(() => null)
const row2After = (await rows.nth(1).boundingBox()).y
check('Cut-off #1 → lead preview appears automatically on the outer side', kind === 'outer', `placement=${kind}`)
check('Rows do not move when the preview appears', row2Before === row2After, `${row2Before} → ${row2After}`)
const pb0 = await preview.boundingBox()
const panelBox = await panel.boundingBox()
check('Preview sits on the far side of the panel from the caret', pb0.y >= panelBox.y + panelBox.height, `preview y ${Math.round(pb0.y)} ≥ panel bottom ${Math.round(panelBox.y + panelBox.height)}`)
const beforeBody = await fieldText()
await preview.locator('p').click()
await page.waitForTimeout(200)
check('Clicking the preview body inserts nothing and keeps focus', (await fieldText()) === beforeBody && (await focusedIsField()))
await preview.hover()
await page.mouse.wheel(0, 120)
await page.waitForTimeout(150)
check('Wheel over the preview keeps focus', await focusedIsField())
await page.keyboard.press('Alt+ArrowDown')
await page.waitForTimeout(200)
const chip = (await preview.locator('span.tnum').first().innerText()).trim()
check('Alt+↓ moves the preview to candidate 2', chip === '2', `chip=${chip}`)
await page.keyboard.press('Alt+Backquote')
await page.waitForTimeout(200)
const hiddenNow = (await preview.count()) === 0
await page.keyboard.press('Alt+Backquote')
await page.waitForTimeout(300)
check('Alt+` hides and shows the preview', hiddenNow && (await preview.count()) === 1)
await preview.getByRole('button', { name: 'Hide full text' }).click()
await page.waitForTimeout(200)
check('× collapses the preview for this composition; focus kept', (await preview.count()) === 0 && (await focusedIsField()))
await page.keyboard.press('Alt+Backquote')
await page.waitForTimeout(300)
await preview.getByRole('button', { name: /Insert/ }).click()
await page.waitForTimeout(400)
check('Preview Insert inserts the previewed candidate; preview closes with the composition', (await fieldText()).includes("We'll discuss this") && (await preview.count()) === 0, JSON.stringify((await fieldText()).slice(-40)))
await page.screenshot({ path: `${out}/after-preview-insert.png`, clip: { x: 40, y: 360, width: 600, height: 90 } })

// 9. Unavailable item.
await scenario('Partial')
const before9 = await fieldText()
await page.keyboard.press('Alt+Digit2')
await page.waitForTimeout(150)
const notice = await page.getByText('Nothing to insert yet').isVisible().catch(() => false)
await page.screenshot({ path: `${out}/unavailable.png`, clip: await around() })
check('Alt+2 on a loading item → notice, no insert', notice && (await fieldText()) === before9)

// 10. Quick target switch from the footer.
await scenario('Short')
await page.getByRole('button', { name: 'Translate into' }).click()
await page.waitForTimeout(200)
await page.screenshot({ path: `${out}/target-menu.png`, clip: await around() })
await page.getByRole('menuitem', { name: '日本語' }).click()
await page.waitForTimeout(1200)
const first = await rows.nth(0).innerText()
check('Footer switch changes target language immediately', /時間/.test(first), first.replace(/\s+/g, ' '))
check('Field keeps focus after switching language', await focusedIsField())
await page.getByRole('button', { name: 'Translate into' }).click()
await page.getByRole('menuitem', { name: 'English' }).click()
await page.waitForTimeout(800)

// 11. Alt+0, pause, settings shortcut.
await page.keyboard.press('Alt+Digit0')
await page.waitForTimeout(100)
const hidden = (await panel.count()) === 0
await page.keyboard.press('Alt+Digit0')
await page.waitForTimeout(100)
check('Alt+0 hides and shows the panel', hidden && (await panel.count()) === 1)
await page.keyboard.press('Control+Alt+KeyP')
await page.waitForTimeout(150)
const pausedShown = await page.getByText('Translation paused').first().isVisible().catch(() => false)
await page.keyboard.press('Control+Alt+KeyP')
await page.waitForTimeout(150)
check('Ctrl+Alt+P pauses and resumes', pausedShown && (await panel.count()) === 1)
await page.keyboard.press('Escape')
await page.keyboard.press('Control+Alt+KeyO')
await page.waitForTimeout(250)
check('Ctrl+Alt+O opens settings', await page.getByRole('dialog', { name: 'Settings' }).isVisible())
const dlg = page.getByRole('dialog')

// 12. Density previews live; Cancel reverts.
await dlg.getByRole('button', { name: 'Appearance' }).click()
await dlg.getByRole('radio', { name: 'Compact' }).click()
await page.waitForTimeout(150)
const dirty = await page.getByText('1 unsaved change').isVisible()
await dlg.screenshot({ path: `${out}/settings-density-preview.png` })
await page.getByRole('button', { name: 'Cancel' }).click()
await page.waitForTimeout(150)
check('Density previews live, counted as unsaved, Cancel reverts', dirty && (await dlg.getByRole('radio', { name: 'Comfortable' }).getAttribute('data-state')) === 'checked')

// 12b. Full-text preview mode setting exists, previews live, Cancel reverts.
const leadGroup = dlg.getByRole('radiogroup', { name: 'Full text of candidate 1' })
await leadGroup.getByRole('radio', { name: 'Off' }).click()
await page.waitForTimeout(150)
const offDirty = await page.getByText('1 unsaved change').isVisible()
await leadGroup.scrollIntoViewIfNeeded()
await dlg.screenshot({ path: `${out}/settings-lead-mode.png` })
await page.getByRole('button', { name: 'Cancel' }).click()
await page.waitForTimeout(150)
check('Full-text mode setting (Automatic/On request/Off) previews live; Cancel reverts', offDirty && (await leadGroup.getByRole('radio', { name: 'Automatic' }).getAttribute('data-state')) === 'checked')

// 13. Language preview keeps page; Cancel restores.
await dlg.getByRole('button', { name: 'General' }).click()
await dlg.getByRole('combobox', { name: 'Interface language' }).click()
await page.getByRole('option', { name: '日本語' }).click()
await page.waitForTimeout(200)
const ja = await dlg.getByRole('heading', { name: '一般' }).isVisible()
await page.getByRole('button', { name: 'キャンセル' }).click()
await page.waitForTimeout(200)
check('Interface language previews on the same page; Cancel restores', ja && (await dlg.getByRole('heading', { name: 'General' }).isVisible()))

// 14. Save persists.
await dlg.getByRole('combobox', { name: 'Candidates to translate' }).click()
await page.getByRole('option', { name: '7', exact: true }).click()
await page.getByRole('button', { name: 'Save', exact: true }).click()
await dlg.getByRole('button', { name: 'Close' }).click()
await page.keyboard.press('Control+Alt+KeyO')
await page.waitForTimeout(200)
check('Saved value survives close + reopen', (await page.getByRole('combobox', { name: 'Candidates to translate' }).innerText()).trim() === '7')
await page.getByRole('dialog').getByRole('button', { name: 'Close' }).click()

// 15. Screen edge.
await page.getByRole('button', { name: 'Bottom-right', exact: true }).click()
await page.waitForTimeout(2600)
const pb = await panel.boundingBox()
const fb = await field.boundingBox()
check('Near bottom edge: panel placed above the caret', pb.y + pb.height < fb.y, `panel bottom ${Math.round(pb.y + pb.height)} < field top ${Math.round(fb.y)}`)
check('Near right edge: panel stays on screen', pb.x + pb.width <= 1140, `right ${Math.round(pb.x + pb.width)} ≤ 1140`)
await page.screenshot({ path: `${out}/screen-edge.png`, clip: { x: 400, y: 300, width: 740, height: 520 } })

check('No runtime errors', errors.length === 0, errors.join('; '))
await browser.close()
await server.close()
writeFileSync(resolve(out, 'results.json'), JSON.stringify(results, null, 2))
const failed = results.filter((r) => !r.ok).length
console.log(`\n${results.length - failed}/${results.length} passed`)
process.exit(failed ? 1 : 0)
