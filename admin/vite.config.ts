import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const proxyTarget = env.VITE_BACKEND_PROXY_TARGET?.trim()

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes('node_modules')) {
              return undefined
            }
            if (id.includes('/@tiptap/')) {
              return 'tiptap'
            }
            if (id.includes('/primevue/')) {
              const [, primevuePath] = id.split('/primevue/')
              const [componentName] = primevuePath.split('/')
              return `primevue-${componentName}`
            }
            if (id.includes('/@primeuix/')) {
              return 'primeuix'
            }
            if (id.includes('/primeicons/')) {
              return 'primeicons'
            }
            if (
              id.includes('/vue/')
              || id.includes('/vue-router/')
              || id.includes('/pinia/')
            ) {
              return 'vue'
            }
            return 'vendor'
          },
        },
      },
    },
    server: proxyTarget
      ? {
          proxy: {
            '/api': {
              target: proxyTarget,
              changeOrigin: true,
            },
          },
        }
      : undefined,
    test: {
      environment: 'jsdom',
      globals: true,
      css: false,
    },
  }
})
