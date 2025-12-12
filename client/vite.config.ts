import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import basicSsl from '@vitejs/plugin-basic-ssl'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), basicSsl()],
  server: {
    host: '0.0.0.0', // Allow external connections
    port: 3000,
    https: {},      // Enable basic HTTPS
    proxy: {
      '/api': {
        target: 'https://127.0.0.1:9000',
        changeOrigin: true,
        secure: false,
      },
      '/login': {
        target: 'https://127.0.0.1:9000',
        changeOrigin: true,
        secure: false,
      },
      '/logout': {
        target: 'https://127.0.0.1:9000',
        changeOrigin: true,
        secure: false,
      },
      '/admin': {
        target: 'https://127.0.0.1:9000',
        changeOrigin: true,
        secure: false,
      }
    }
  }
})
