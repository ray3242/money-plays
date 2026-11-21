import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

export default defineConfig(({ mode }) => ({
  root: fileURLToPath(new URL(`./${mode === 'ledger' ? 'ledger' : 'panel'}`, import.meta.url)),
  base: './',
  plugins: [react()],
  build: { outDir: 'dist', emptyOutDir: true },
  server: { fs: { allow: [fileURLToPath(new URL('../', import.meta.url))] } }
}));
