import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:3001',
        changeOrigin: true,
        secure: false,
      },
    },
  },
  build: {
    // Remove console statements in production builds, keep console.error and console.warn for debugging
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: ['log', 'info', 'debug'],
        drop_debugger: true,
        pure_funcs: ['console.log', 'console.debug', 'console.info']
      }
    },
    // Optimize bundle
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'reactflow'],
          mui: ['@mui/material', '@mui/icons-material'],
          anthropic: ['@anthropic-ai/sdk']
        }
      }
    }
  }
})
