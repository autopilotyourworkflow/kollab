import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Pinned so the README's documented dev URL and the backend's primary CORS
  // origin (backend/app/main.py) are true on any machine.
  server: { port: 5178 },
})
