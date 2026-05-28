/// <reference types="vitest" />

import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

/**
 * Vitest Configuration for Auralis Frontend
 *
 * Testing strategy:
 * - Unit tests: Fast, isolated components (< 100ms)
 * - Integration tests: Multiple components, real Redux state (< 2s)
 * - E2E tests: Full user flows with Playwright
 *
 * Performance targets:
 * - Test suite runs in < 2 minutes
 * - Individual test < 100ms
 * - Coverage > 85%
 * - Memory usage < 1GB
 */

export default defineConfig({
  plugins: [react()],

  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },

  test: {
    // Testing framework: Vitest (fast, Jest-compatible)
    globals: true, // Inject describe, it, expect, vi, etc. without imports
    environment: 'jsdom', // Browser-like DOM for React testing

    // Test files
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['node_modules', 'dist', 'build'],

    // Setup files
    setupFiles: ['./src/test/setup.ts'],
    css: true,

    // Timeout configuration
    testTimeout: 30000, // 30s per test
    hookTimeout: 10000, // 10s per hook (beforeEach, afterEach)
    teardownTimeout: 10000, // 10s to clean up resources

    // Isolation and cleanup
    isolate: true, // Isolate each test file
    clearMocks: true, // Clear mocks between tests
    restoreMocks: true, // Restore original mocks between tests

    // Pool configuration (memory management)
    // CRITICAL: Prevent OOM errors in CI with limited memory
    // Using 'forks' instead of 'threads' for better memory isolation
    // Each fork gets its own V8 heap, preventing accumulation across tests
    pool: 'forks',
    // Vitest 4 removed `test.poolOptions`; the per-pool options are now
    // top-level (#3488). `maxForks` -> `maxWorkers`; `minForks` has no v4
    // equivalent; per-fork `isolate` is already covered by `isolate: true`
    // above. `execArgv` (node flags for the test worker subprocesses) stays.
    maxWorkers: 2,
    execArgv: ['--expose-gc', '--max-old-space-size=1024'],

    // Reporter configuration
    reporters: ['default', 'html', 'json'],
    outputFile: {
      html: './test-results/index.html',
      json: './test-results/results.json',
    },

    // Coverage configuration
    coverage: {
      // Coverage provider: v8 (built-in, no dependencies)
      provider: 'v8',

      // Report formats
      reporter: ['text', 'text-summary', 'html', 'json', 'lcov'],
      reportOnFailure: true,

      // Coverage include/exclude
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'node_modules/',
        'src/test/', // Test infrastructure
        '**/*.d.ts', // Type definitions
        '**/*.config.*', // Config files
        '**/mockData', // Mock data
        'src/**/*.stories.tsx', // Storybook files
        'src/**/*.test.{ts,tsx}', // Test files themselves
        'build/',
        'dist/',
      ],

      // Minimum coverage thresholds (Vitest 4: moved under `thresholds`,
      // and `coverage.all` was removed — #3488).
      thresholds: {
        lines: 85,
        functions: 85,
        branches: 80,
        statements: 85,
      },
      skipFull: false, // Report all files, even with 100% coverage
    },

    // Performance options
    benchmark: {
      include: ['src/**/*.bench.{ts,tsx}'],
      exclude: ['node_modules', 'dist', 'build'],
      outputFile: './test-results/bench.json',
    },

    // TypeScript support
    typecheck: {
      enabled: false, // Disable inline type checking for speed
      // Run `npm run test:types` separately for type checking
    },

    // API options
    api: false, // Disable API by default (faster)

    // Snapshot options. Vitest 4's pretty-format dropped `escapeControlCharacters`
    // (#3488); the remaining keys are unchanged.
    snapshotFormat: {
      escapeString: false,
      printBasicPrototype: false,
    },

    // Inline snapshots
    snapshotSerializers: [],

    // Mockable modules. The valid key is `restoreMocks` (set above);
    // `restoreAllMocks` was a non-option that v4's stricter types now reject.
    mockReset: true,
  },

  define: {
    'process.env.NODE_ENV': '"test"',
    'process.env.VITE_API_URL': '"http://localhost:8765/api"',
  },
});
