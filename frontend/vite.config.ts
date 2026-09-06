/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// CE-C01: dev cross-origin is handled by a Vite proxy (no backend CORS).
// `/api/*` requests from the dev server are forwarded to the FastAPI backend.
// CE-DEP02: the deployed frontend is served from the `/CHIA/` path on GitHub
// Pages (https://ksprinkle.github.io/CHIA/). `base` drives every built asset
// URL and `import.meta.env.BASE_URL` (consumed by the router basename and the
// committed TopoJSON asset paths). The dev proxy below is unaffected.
export default defineConfig({
  base: '/CHIA/',
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    // CE-DEP02: the simulated browser sits under the same `/CHIA/` base the
    // deployed app is served from, so the real `createBrowserRouter`
    // (basename = import.meta.env.BASE_URL) matches in `App.test.tsx`.
    // Memory-router tests pass explicit `initialEntries` and are unaffected.
    environmentOptions: { jsdom: { url: 'http://localhost:3000/CHIA/' } },
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
