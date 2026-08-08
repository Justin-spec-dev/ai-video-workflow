import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// SPEC §0: dev server on 5173, proxy /api and /ws to backend on 8000.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
});
