import { defineConfig, defineConfig as vitestDefineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { execSync } from 'child_process'

// Function to get current commit hash (called fresh each time in dev mode)
function getCommitId(): string {
  try {
    return execSync('git rev-parse --short HEAD', { encoding: 'utf8' }).trim()
  } catch {
    return 'unknown'
  }
}

export default defineConfig(({ mode }) => {
  // Get commit at config time for build mode
  const commitIdAtBuildTime = getCommitId()

  return {
    plugins: [
      react(),
      {
        name: 'inject-commit-id',
        transformIndexHtml(html: string) {
          // In dev mode, get fresh commit hash for each request
          // In build mode, use the commit from config time
          const commitId = mode === 'serve' ? getCommitId() : commitIdAtBuildTime
          return html.replace('%VITE_COMMIT_ID%', commitId)
        },
      },
    ],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    define: {
      'process.env.NODE_ENV': mode === 'test' ? '"development"' : `"${mode}"`,
      'process.env.VITE_COMMIT_ID': `"${commitIdAtBuildTime}"`,
    },
    server: {
      port: 3000,
      open: false,
      proxy: {
        '/api': {
          target: 'http://localhost:8765',
          changeOrigin: true,
        },
        '/ws': {
          target: 'ws://localhost:8765',
          ws: true,
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: 'build',
      sourcemap: false,
      rollupOptions: {
        output: {
          // Disable automatic chunking to prevent missing chunk errors
          manualChunks: undefined,
        },
      },
    },
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      css: true,
      // Memory management: limit concurrent test threads to prevent memory explosion
      threads: true,
      maxThreads: 2,
      minThreads: 1,
      // Timeout settings for memory cleanup
      testTimeout: 30000,
      hookTimeout: 10000,
      // Force exit after tests complete (prevents hanging)
      forceExitTimeout: 5000,
      // Per-test isolation for better cleanup
      isolate: true,
      // Clear mocks between tests
      clearMocks: true,
      // Restore mocks between tests
      restoreMocks: true,
      coverage: {
        provider: 'v8',
        reporter: ['text', 'json', 'html'],
        exclude: [
          'node_modules/',
          'src/test/',
          '**/*.d.ts',
          '**/*.config.*',
          '**/mockData',
          'build/',
        ],
      },
    },
  }
})
