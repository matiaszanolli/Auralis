import { defineConfig } from 'vite'
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
        transformIndexHtml: {
          order: 'pre',
          handler(html: string) {
            // In dev mode, get fresh commit hash for each request
            // In build mode, use the commit from config time
            const commitId = mode === 'serve' ? getCommitId() : commitIdAtBuildTime
            return html.replace('%VITE_COMMIT_ID%', commitId)
          },
        },
      },
      {
        name: 'fix-vendor-loading-order',
        transformIndexHtml: {
          order: 'post',
          handler(html: string) {
            if (mode === 'serve') return html

            // Find vendor and app script tags
            const vendorMatch = html.match(/<link rel="modulepreload"[^>]*href="\/[^"]*vendor[^"]*"[^>]*>/)
            const appScriptMatch = html.match(/<script type="module"[^>]*src="\/[^"]*\/(assets\/)?index[^"]*"[^>]*><\/script>/)

            if (!vendorMatch || !appScriptMatch) return html

            // Extract the vendor filename
            const vendorHref = vendorMatch[0].match(/href="([^"]*)"/)?.[1]
            if (!vendorHref) return html

            // Replace with a synchronous script that ensures vendor loads first
            // Use a blocking pattern to prevent race conditions
            const appSrc = appScriptMatch[0].match(/src="([^"]*)"/)?.[1] || '/assets/index.js'
            const newScript = `<script type="module">
  // Ensure vendor dependencies are loaded and evaluated before app code runs
  (async () => {
    try {
      // Load vendor chunk first - this is critical!
      await import('${vendorHref}');
      // Small delay to ensure vendor is fully initialized
      await new Promise(resolve => setTimeout(resolve, 0));
      // Now safe to load app code
      await import('${appSrc}');
    } catch (error) {
      console.error('Failed to load application:', error);
      // Show error page if loading fails
      document.documentElement.innerHTML = '<body style="background:#1a1a1a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0"><div style="text-align:center"><h1>Loading Error</h1><p>' + error.message + '</p></div></body>';
    }
  })();
</script>`

            return html
              .replace(/<link rel="modulepreload"[^>]*href="\/[^"]*vendor[^"]*"[^>]*>/, '') // Remove modulepreload
              .replace(/<script type="module"[^>]*src="\/[^"]*\/(assets\/)?index[^"]*"[^>]*><\/script>/, newScript)
          },
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
          // Separate vendor chunk for better module initialization order
          // Critical: This prevents 'Paper is not defined' errors in Electron/AppImage
          // by ensuring React, ReactDOM, and MUI load before application code
          manualChunks: (id) => {
            // Explicitly put vendor libraries in vendor chunk
            if (
              id.includes('node_modules/react') ||
              id.includes('node_modules/@mui') ||
              id.includes('node_modules/@emotion')
            ) {
              return 'vendor'
            }
          },
          chunkFileNames: '[name]-[hash].js',
        },
      },
      // Increase chunk size warning threshold
      chunkSizeWarningLimit: 1000,
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
