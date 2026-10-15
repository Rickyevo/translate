import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'node:path'

// Renderer build: two small pages (panel, settings). Shared UI comes from ../prototype/src;
// every package is resolved from this app so there is exactly one React.
const shared = ['react', 'react-dom', 'zustand', 'i18next', 'react-i18next', 'lucide-react', '@fontsource-variable/inter']
const radix = ['dropdown-menu', 'tooltip', 'switch', 'select', 'slider', 'popover', 'radio-group', 'context-menu'].map((n) => '@radix-ui/react-' + n)

export default defineConfig({
  root: resolve(__dirname, 'src/renderer'),
  base: './',
  plugins: [react(), tailwindcss()],
  cacheDir: resolve(__dirname, '../.cache/vite-app'),
  resolve: {
    dedupe: [...shared, ...radix],
  },
  build: {
    outDir: resolve(__dirname, 'dist/renderer'),
    emptyOutDir: true,
    target: 'chrome140',
    modulePreload: false,
    reportCompressedSize: false,
    rollupOptions: { input: { panel: resolve(__dirname, 'src/renderer/panel.html'), settings: resolve(__dirname, 'src/renderer/settings.html') } },
  },
})
