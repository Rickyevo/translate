// Bundles main + preload with esbuild (CommonJS, Electron externals).
import { build } from 'esbuild'
const common = { bundle: true, platform: 'node', target: 'node22', format: 'cjs', external: ['electron'], minify: true, sourcemap: false, logLevel: 'warning' }
await build({ ...common, entryPoints: ['src/main/main.ts'], outfile: 'dist/main/main.js' })
await build({ ...common, entryPoints: ['src/preload/preload.ts'], outfile: 'dist/preload/preload.js' })
console.log('main + preload built')
