import {defineConfig, loadEnv} from 'vite';
import react from '@vitejs/plugin-react';
import tailwind from '@tailwindcss/vite';

export default defineConfig(({command, mode}) => {
  const env=loadEnv(mode, process.cwd(), '')
  return {
    base: env.VITE_BASE_PATH || (command === 'serve' ? '/library/' : '/life-Library/'),
    plugins: [react(), tailwind()],
    server: {host: true, proxy: {'/api': env.VITE_DEV_API_TARGET || 'http://127.0.0.1:8000'}},
  }
})
