import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  const target = env.VITE_API_BASE_URL || 'http://localhost:8000'
  const parsed = new URL(target)
  if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password) {
    throw new Error('VITE_API_BASE_URL must be an HTTP(S) origin without credentials')
  }
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/health': { target: parsed.origin, changeOrigin: true },
        '/api': { target: parsed.origin, changeOrigin: true },
      },
    },
  }
})
