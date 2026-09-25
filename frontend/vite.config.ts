import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import tailwind from '@tailwindcss/vite';

export default defineConfig(({command}) => ({
  base: process.env.VITE_BASE_PATH || (command === 'serve' ? '/library/' : '/life-Library/'),
  plugins: [react(), tailwind()],
  server: {host: true, proxy: {'/api': 'http://localhost:8000'}},
}))
