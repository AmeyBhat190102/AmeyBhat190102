import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The dev server proxies /api to the backend so the browser makes same-origin
// requests and CORS never enters the picture during development.
const proxy = {
  '/api': {
    target: process.env.VITE_API_TARGET || 'http://127.0.0.1:8000',
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api/, ''),
  },
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, proxy },
  // `npm run preview` serves the production build, so it needs the same proxy.
  preview: { port: 4173, proxy },
})
