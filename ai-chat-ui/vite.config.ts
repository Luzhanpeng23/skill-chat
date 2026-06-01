import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { defineConfig } from 'vite'
import tsconfigPaths from 'vite-tsconfig-paths'
// import { analyzer } from 'vite-bundle-analyzer'

// 当前仓库的 Python 后端默认跑在 8000，必要时仍可通过环境变量覆盖。
const BACKEND_DEV_SERVER_PORT = process.env.BACKEND_PORT ?? 8000
const BUILD_BASE = '/'

// https://vite.dev/config/
export default defineConfig(({ command }) => ({
  plugins: [react(), tailwindcss(), tsconfigPaths({ root: __dirname })],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  base: command === 'build' ? BUILD_BASE : '',
  build: {
    outDir: path.resolve(__dirname, '..', 'web'),
    emptyOutDir: true,
    assetsDir: 'assets',
  },
  server: {
    proxy: {
      '/api': {
        target: `http://localhost:${BACKEND_DEV_SERVER_PORT}/`,
        changeOrigin: true,
      },
    },
  },
}))
