import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { join } from 'path';

export default defineConfig({
  plugins: [react()],
  base: './',
  root: join(__dirname, 'src/renderer'),
  publicDir: 'public',
  build: {
    outDir: '../../dist/renderer',
    emptyOutDir: true
  },
  server: {
    port: 5177
  }
});
