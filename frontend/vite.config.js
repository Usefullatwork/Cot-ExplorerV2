import { defineConfig } from 'vite';

export default defineConfig({
  base: './',
  test: {
    environment: 'jsdom',
    globals: true,
    pool: 'forks',
    poolOptions: { forks: { singleFork: true } },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            // Prevent double-encoding of UTF-8 Norwegian characters
            delete proxyRes.headers['content-encoding'];
          });
        },
      },
      '/health': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '/metrics': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    rollupOptions: {
      output: {
        manualChunks: {
          chart: ['chart.js'],
          lwc: ['lightweight-charts'],
        },
      },
    },
  },
});
