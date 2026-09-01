import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Bind both IPv4 and IPv6 loopback -- without this Vite can end up
    // listening on ::1 only, so http://127.0.0.1:5173 fails to connect
    // even though http://localhost:5173 happens to resolve to the same
    // process. Explicit host avoids depending on which one a given
    // browser/OS picks.
    host: true,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
