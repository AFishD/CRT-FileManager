import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: '/',  // 修改：使用根路径，避免资源路径问题
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    // 优化构建配置
    minify: 'esbuild',  // 使用esbuild进行压缩，速度更快
    esbuildOptions: {
      target: 'es2015'  // 设置目标ES版本
    },
    // 启用gzip压缩大小报告
    reportCompressedSize: false,  // 关闭报告以加快构建速度
    // 设置chunk大小限制
    chunkSizeWarningLimit: 500
    // 移除manualChunks配置，避免chunk冲突
  }
})