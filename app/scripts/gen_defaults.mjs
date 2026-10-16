// Writes src-tauri/defaults.json from the UI's DEFAULT_SETTINGS (prototype/src/model.ts), so the host and the UI
// share one source of truth. Run from app/:  node scripts/gen_defaults.mjs
import { build } from 'esbuild'
import { writeFileSync } from 'node:fs'
const out = await build({
  stdin: { contents: "import { DEFAULT_SETTINGS } from '../prototype/src/model'; console.log(JSON.stringify(DEFAULT_SETTINGS, null, 2))", resolveDir: '.', loader: 'ts' },
  bundle: true, platform: 'node', write: false, format: 'cjs', logLevel: 'warning',
})
const json = await new Promise((resolve, reject) => {
  const lines = []
  const orig = console.log
  console.log = (s) => lines.push(s)
  try { new Function('require', 'module', out.outputFiles[0].text)(() => ({}), { exports: {} }) } catch (e) { reject(e) } finally { console.log = orig }
  resolve(lines.join('\n'))
})
writeFileSync('src-tauri/defaults.json', json + '\n')
console.log('src-tauri/defaults.json')
