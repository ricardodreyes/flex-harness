import { defineConfig } from 'vite';

export default defineConfig({
  server: { proxy: { '/api/replay': 'http://127.0.0.1:4174' } },
});
