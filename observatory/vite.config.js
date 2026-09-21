import { defineConfig } from 'vite';
import cesium from 'vite-plugin-cesium';
export default defineConfig({
  root: 'observatory',
  base: './',
  plugins: [cesium()],
  server: {
    host: '127.0.0.1',
    port: 4180,
    fs: {
      allow: ['..'],
      deny: ['.env', '.env.*', '**/.git/**', '**/.venv/**', '**/data/raw/**'],
    },
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  build: { outDir: '../dist-observatory', emptyOutDir: true },
});
