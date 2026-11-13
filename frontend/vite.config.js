import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  // In development the UI runs on :5173 and the backend on :8000; in production one server serves both.
  server: {
    // API_TARGET is set by docker-compose.dev.yml (the api container); on a plain machine it is the local backend.
    proxy: {
      '/api': process.env.API_TARGET || 'http://localhost:8000',
      '/images': process.env.API_TARGET || 'http://localhost:8000',
    },
    // file-change events do not reach a container from a mounted Windows/macOS folder, so poll there
    watch: process.env.CHOKIDAR_USEPOLLING ? { usePolling: true, interval: 300 } : undefined,
  },
})
