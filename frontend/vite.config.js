import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig(({ command }) => ({
  base: process.env.VITE_BASE_PATH || (command === 'build' ? '/security/' : '/'),
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 4173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
    },
  },
}))
