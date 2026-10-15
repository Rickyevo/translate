// Production package: bundled main/preload/renderer only (no node_modules), asar, Overlap icon, the Python backend
// and an isolated Python 3.12 runtime next to app.asar (resources/backend, resources/python): the release needs no
// Python, Node or any other development tool on the machine. Build with CPython 3.12 on PATH.
import { packager } from '@electron/packager'
import { flipFuses, FuseVersion, FuseV1Options } from '@electron/fuses'
import { copyFileSync, cpSync, readdirSync, rmSync } from 'node:fs'
import { execFileSync } from 'node:child_process'
import { join } from 'node:path'

// --out=<dir> packages elsewhere (e.g. while Translate.exe is running from out/ and locks it).
const OUT = process.argv.find((a) => a.startsWith('--out='))?.slice(6) ?? 'out'
rmSync(OUT, { recursive: true, force: true })
// Ship only the runtime backend: no tests, no research/capture tools (they can write raw pipe data to
// disk), no bytecode caches.
const STAGE = '../.cache/package-stage/backend'
rmSync(STAGE, { recursive: true, force: true })
for (const part of ['translate_backend', 'vendor', 'requirements.txt'])
  cpSync(join('../backend', part), join(STAGE, part), { recursive: true, filter: (src) => !/__pycache__|\.pyc$/.test(src) })
// Isolated runtime (+ precompiled backend); see scripts/bundle_python.py.
const PY_STAGE = '../.cache/package-stage/python'
execFileSync('python', ['-X', 'utf8', 'scripts/bundle_python.py', PY_STAGE, STAGE], { stdio: 'inherit' })
const paths = await packager({
  dir: '.',
  out: OUT,
  name: 'Translate',
  executableName: 'Translate',
  platform: 'win32',
  arch: 'x64',
  asar: true,
  prune: true,
  icon: 'build/icon.ico',
  overwrite: true,
  extraResource: [STAGE, PY_STAGE],
  appVersion: JSON.parse((await import('node:fs')).readFileSync('package.json', 'utf8')).version,
  appCopyright: 'Translate',
  win32metadata: { CompanyName: 'Translate', FileDescription: 'Translate', ProductName: 'Translate' },
  // Only the built output and package.json go into app.asar.
  ignore: (p) => p !== '' && !/^\/(dist|package\.json)(\/|$)/.test(p),
  download: { cacheRoot: '../.cache/electron' },
})
// Keep only the Chromium UI locales we ship (≈49 MB → ≈2 MB). Disk only; no effect on memory.
const KEEP = new Set(['en-US.pak', 'zh-CN.pak', 'ja.pak', 'ko.pak'])
for (const p of paths) for (const f of readdirSync(join(p, 'locales'))) if (!KEEP.has(f)) rmSync(join(p, 'locales', f))
// Harden the executable: it can't be used as a generic Node runtime or debugged via CLI flags,
// and it only loads the app.asar it shipped with.
for (const p of paths)
  await flipFuses(join(p, 'Translate.exe'), {
    version: FuseVersion.V1,
    [FuseV1Options.RunAsNode]: false,
    [FuseV1Options.EnableNodeOptionsEnvironmentVariable]: false,
    [FuseV1Options.EnableNodeCliInspectArguments]: false,
    [FuseV1Options.EnableEmbeddedAsarIntegrityValidation]: true,
    [FuseV1Options.OnlyLoadAppFromAsar]: true,
    [FuseV1Options.EnableCookieEncryption]: true,
  })
for (const p of paths) copyFileSync('build/THIRD_PARTY_NOTICES.txt', join(p, 'THIRD_PARTY_NOTICES.txt'))
console.log('packaged:', paths.join(', '))
