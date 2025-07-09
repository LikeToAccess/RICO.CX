import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:9000',
        changeOrigin: true,
        secure: false,
      },
      '/login': {
        target: 'http://localhost:9000',
        changeOrigin: true,
        secure: false,
      },
      '/logout': {
        target: 'http://localhost:9000',
        changeOrigin: true,
        secure: false,
      },
      '/admin': {
        target: 'http://localhost:9000',
        changeOrigin: true,
        secure: false,
      }
    }
  }
})
