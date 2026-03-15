import { URL, fileURLToPath } from 'node:url'

import autoprefixer from 'autoprefixer'
import basicSsl from '@vitejs/plugin-basic-ssl'
import { defineConfig } from 'vite'
import tailwindcss from 'tailwindcss'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    basicSsl(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 3080,
    https: true,
    allowedHosts:  [
      'workspace0i1i272n8yslpxd3hm-3080.gz.cloudide.woa.com',
      'workspace0i1i272n8yslpxd3hm-3080.gz.cloudide.woa.com',
    ],
    proxy: {
      '/api': {
        target: 'http://localhost:3090',
        changeOrigin: true,
        ws: true,
      }
    }
  },
  css: {
    postcss: {
      plugins: [
        tailwindcss,
        autoprefixer,
      ],
    },
    preprocessorOptions: {
      scss: {
        silenceDeprecations: ['import', 'legacy-js-api']
      }
    }
  }
})