import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import tailwind from '@tailwindcss/vite';

export default defineConfig({
  base: '/life-Library/',
  plugins: [react(), tailwind()],
  server: {host: true, proxy: {'/api': 'http://localhost:8000'}},
})
