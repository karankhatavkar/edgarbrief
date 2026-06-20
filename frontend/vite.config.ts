import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  // Dev only: the app calls a relative /api so the same VITE_API_BASE_URL=/api
  // works in dev and in the single-container prod build. Under `pnpm dev` the
  // Vite server (:5173) forwards /api to the local FastAPI backend (:8000).
  // Not used in production, where FastAPI serves the build and /api is same-origin.
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
