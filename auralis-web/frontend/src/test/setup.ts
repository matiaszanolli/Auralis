/**
 * Test setup file for Vitest
 * Configures global test environment, matchers, and polyfills
 */

import '@testing-library/jest-dom'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeAll, afterAll, vi } from 'vitest'
import { server } from './mocks/server'

// Create jest global alias for Vitest compatibility
// This allows jest.mock() calls to work in tests
;(globalThis as any).jest = {
  mock: vi.mock,
  unmock: vi.unmock,
  doMock: vi.doMock,
  doUnmock: vi.doUnmock,
  fn: vi.fn,
  spyOn: vi.spyOn,
  clearAllMocks: vi.clearAllMocks,
}

// Cleanup after each test case with aggressive memory management
afterEach(async () => {
  // 1. React Testing Library cleanup (unmount all components)
  cleanup()

  // 2. Clear all vi mocks
  vi.clearAllMocks()

  // 3. Clear jest timer mocks
  vi.useRealTimers()

  // 4. Force garbage collection if available (V8)
  if (global.gc) {
    global.gc()
  }

  // 5. Small delay to allow cleanup to complete
  await new Promise(resolve => setTimeout(resolve, 0))
})

// Mock window.matchMedia (used by MUI components for responsive design)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query) => {
    // Simulate responsive behavior based on query
    // Default to desktop size (1920x1080) unless specific breakpoint is requested
    let matches = false;

    if (query) {
      // Common MUI breakpoints
      if (query.includes('max-width: 400px')) {
        matches = true; // xs
      } else if (query.includes('max-width: 600px')) {
        matches = true; // sm
      } else if (query.includes('max-width: 900px')) {
        matches = false; // md (default desktop)
      } else if (query.includes('max-width: 1200px')) {
        matches = false; // lg
      } else if (query.includes('max-width: 1536px')) {
        matches = false; // xl
      } else if (query.includes('(prefers-color-scheme: dark)')) {
        matches = true; // dark mode (assume dark for tests)
      } else if (query.includes('(prefers-reduced-motion: reduce)')) {
        matches = false; // animation enabled (default)
      }
    }

    return {
      matches,
      media: query,
      onchange: null,
      addListener: vi.fn(), // deprecated
      removeListener: vi.fn(), // deprecated
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    };
  }),
})

// Mock IntersectionObserver (used by virtualization libraries)
// Create a factory function so tests can spy on and override the constructor
const createIntersectionObserverMock = () => vi.fn(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
  takeRecords: vi.fn(() => []),
}));

global.IntersectionObserver = createIntersectionObserverMock() as any

// Mock ResizeObserver (used by some UI components)
global.ResizeObserver = class ResizeObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  unobserve() {}
} as any

// Mock WebSocket
global.WebSocket = class WebSocket {
  constructor(public url: string) {}
  close() {}
  send() {}
  addEventListener() {}
  removeEventListener() {}
  CONNECTING = 0
  OPEN = 1
  CLOSING = 2
  CLOSED = 3
  readyState = 3
} as any

// Mock Element.scrollTo (used by auto-scroll features)
Element.prototype.scrollTo = vi.fn()

// Suppress act() warnings for WebSocket and event handlers (inherently async)
// These warnings are expected for event-driven state updates outside of React render cycles
const originalError = console.error
vi.spyOn(console, 'error').mockImplementation((...args: any[]) => {
  // Suppress "An update to X inside a test was not wrapped in act(...)" warnings
  // These occur in event handlers (WebSocket, timeouts) which are inherently async
  if (args[0]?.toString?.().includes('not wrapped in act')) {
    return
  }
  // Suppress React Router future flag warnings (expected, non-blocking)
  if (args[0]?.toString?.().includes('React Router Future Flag Warning')) {
    return
  }
  // Log all other errors normally
  originalError(...args)
})

// ============================================================
// MSW Server Lifecycle with Memory Management
// ============================================================

// Start MSW server before all tests
beforeAll(() => {
  server.listen({
    onUnhandledRequest: (request) => {
      // Suppress warnings for WebSocket connections (mocked in test environment)
      const url = new URL(request.url);
      if (url.protocol === 'ws:' || url.protocol === 'wss:') {
        return;
      }
      console.warn(`[MSW] Warning: unhandled ${request.method} ${request.url}`);
    }
  })
})

// Reset handlers after each test with proper cleanup
afterEach(async () => {
  // 1. Reset all MSW handlers
  server.resetHandlers()

  // 2. Clear any pending requests
  await new Promise(resolve => setTimeout(resolve, 0))
})

// Clean up after all tests - comprehensive cleanup
afterAll(async () => {
  // 1. Stop MSW server
  server.close()

  // 2. Clear any remaining timeouts
  vi.clearAllTimers()

  // 3. Final garbage collection
  if (global.gc) {
    global.gc()
  }

  // 4. Wait for cleanup
  await new Promise(resolve => setTimeout(resolve, 100))
})
