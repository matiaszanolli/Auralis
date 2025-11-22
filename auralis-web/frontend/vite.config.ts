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

            // Extract app src
            const appSrc = appScriptMatch[0].match(/src="([^"]*)"/)?.[1] || '/assets/index.js'

            // Strategy: Remove modulepreload link completely to prevent race condition.
            // Instead, use a loader script that explicitly loads vendor first,
            // then loads the app which has static imports from vendor.
            //
            // The key: by the time `import(appSrc)` executes, vendor is already
            // fully loaded and initialized, so the static imports in app.js
            // will reuse the vendor module instead of triggering a new load.
            const loaderScript = `<script type="module">
  (async () => {
    try {
      console.log('[loader] Pre-loading vendor module...');

      // Load vendor module
      const vendor = await import('${vendorHref}');
      console.log('[loader] Vendor module imported, checking for MUI...');

      // Wait multiple event loop cycles to ensure all vendor initialization is complete
      // Vendor module contains React, MUI, emotion which register themselves on load
      for (let i = 0; i < 5; i++) {
        await new Promise(r => setTimeout(r, 0));
      }

      console.log('[loader] Vendor initialization complete, loading application...');

      // Now load app - its static imports will reuse vendor from module cache
      const appModule = await import('${appSrc}');
      console.log('[loader] Application loaded successfully');

    } catch (err) {
      console.error('[loader] Fatal loading error:', err);
      const msg = (err && err.message) || 'Unknown error';
      const stack = (err && err.stack) || '';
      console.error('[loader] Full error:', {msg, stack});
      document.documentElement.innerHTML = '<body style="background:#1a1a1a;color:#fff;font-family:sans-serif;margin:0;padding:0;display:flex;align-items:center;justify-content:center;height:100vh"><div style="text-align:center;max-width:700px;padding:40px"><h1 style="color:#ff6b6b;margin:0 0 20px;font-size:28px">Application Error</h1><p style="color:#ccc;margin:0 0 20px;font-size:16px">Failed to load modules</p><p style="color:#999;margin:0 0 20px;font-size:14px;font-family:monospace">' + msg + '</p><details style="text-align:left;margin:30px 0;padding:20px;background:#222;border:1px solid #444;border-radius:6px"><summary style="color:#667eea;cursor:pointer;font-weight:bold;margin-bottom:10px">Stack Trace</summary><pre style="color:#888;font-size:11px;overflow-x:auto;margin:0;white-space:pre-wrap;word-break:break-word;line-height:1.4">' + stack.replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</pre></details><hr style="border:none;border-top:1px solid #333;margin:20px 0"><p style="color:#666;font-size:12px;margin:20px 0">Vendor: ${vendorHref}<br>App: ${appSrc}</p></div></body>';
    }
  })();
</script>`

            return html
              .replace(/<link rel="modulepreload"[^>]*href="\/[^"]*vendor[^"]*"[^>]*>/, '') // Remove modulepreload to eliminate race
              .replace(/<script type="module"[^>]*src="\/[^"]*\/(assets\/)?index[^"]*"[^>]*><\/script>/, loaderScript)
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
