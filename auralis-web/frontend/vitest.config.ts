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
    globals: ['describe', 'it', 'expect', 'beforeEach', 'afterEach', 'vi'], // Use without imports
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
    forceExitTimeout: 5000, // Force exit after 5s if hanging

    // Isolation and cleanup
    isolate: true, // Isolate each test file
    clearMocks: true, // Clear mocks between tests
    restoreMocks: true, // Restore original mocks between tests
    resetModules: false, // Keep module cache between tests

    // Pool configuration (memory management)
    // CRITICAL: Prevent OOM errors in CI with limited memory
    // Using 'forks' instead of 'threads' for better memory isolation
    // Each fork gets its own V8 heap, preventing accumulation across tests
    pool: 'forks',
    poolOptions: {
      forks: {
        // Use limited parallel forks to balance speed and memory
        minForks: 1,
        maxForks: 2,
        // Isolate each test file in its own subprocess
        isolate: true,
        // Exit forks after tests to free memory
        execArgv: ['--expose-gc', '--max-old-space-size=1024'],
      },
    },

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

      // Minimum coverage thresholds
      lines: 85,
      functions: 85,
      branches: 80,
      statements: 85,

      // Fail if coverage below thresholds
      all: true,
      skipFull: false, // Report all files, even with 100% coverage
    },

    // Browser/DOM simulation options
    dom: {
      // Use happy-dom for faster tests (jsdom is slower)
      // Note: This uses jsdom via happy-dom wrapper
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

    // Transformations
    transformMode: {
      web: [/\.[jt]sx$/],
      ssr: [],
    },

    // Environment setup
    environmentSetupModule: undefined,

    // API options
    api: false, // Disable API by default (faster)

    // Snapshot options
    snapshotFormat: {
      escapeString: false,
      printBasicPrototype: false,
      escapeControlCharacters: false,
    },

    // Inline snapshots
    snapshotSerializers: [],

    // Mockable modules
    mockReset: true,
    restoreAllMocks: true,
  },

  define: {
    'process.env.NODE_ENV': '"test"',
    'process.env.VITE_API_URL': '"http://localhost:8765/api"',
  },
});
