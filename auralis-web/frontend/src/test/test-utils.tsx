/**
 * Custom render utilities for testing components with all necessary providers
 *
 * Usage:
 *   import { render, screen } from '@/test/test-utils'
 *
 *   test('renders component', () => {
 *     render(<MyComponent />)
 *     expect(screen.getByText('Hello')).toBeInTheDocument()
 *   })
 */

import { ReactElement, ReactNode } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Provider as ReduxProvider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '@/contexts/ThemeContext'
import { ToastProvider } from '@/components/shared/Toast'
import playerReducer from '@/store/slices/playerSlice'
import queueReducer from '@/store/slices/queueSlice'
import cacheReducer from '@/store/slices/cacheSlice'
import connectionReducer from '@/store/slices/connectionSlice'

// NOTE: the WebSocket context is mocked globally via vi.mock('@/contexts/
// WebSocketContext') in src/test/setup.ts. The former MockWebSocketProvider
// here wrapped a *different*, private context that no production component read,
// so it was dead code and has been removed (#3964). Components under test pull
// the real (mocked) useWebSocketContext from the actual module.

/**
 * Wrapper component that provides all necessary context providers
 * Uses MOCK providers to avoid WebSocket singleton issues in tests
 */
interface AllProvidersProps {
  children: ReactNode
}

/**
 * Create a fresh Redux store for each test to ensure isolation
 * This prevents state leakage between tests.
 *
 * #3613: accepts an optional `preloadedState` so tests can seed
 * player/queue state without firing a chain of dispatches — drives
 * behavior tests that depend on the rendered state (e.g. "shows pause
 * icon when playing").
 */
export type PreloadedState = Partial<{
  player: Partial<ReturnType<typeof playerReducer>>;
  queue: Partial<ReturnType<typeof queueReducer>>;
  cache: Partial<ReturnType<typeof cacheReducer>>;
  connection: Partial<ReturnType<typeof connectionReducer>>;
}>;

export function createTestStore(preloadedState?: PreloadedState) {
  // Build full state by merging preloaded slices over the reducer-provided
  // defaults. Each reducer returns its initial state when handed an unknown
  // action — we use that to populate any unspecified slice.
  const seededState = preloadedState
    ? {
        player: {
          ...playerReducer(undefined, { type: '@@INIT' }),
          ...(preloadedState.player ?? {}),
        },
        queue: {
          ...queueReducer(undefined, { type: '@@INIT' }),
          ...(preloadedState.queue ?? {}),
        },
        cache: {
          ...cacheReducer(undefined, { type: '@@INIT' }),
          ...(preloadedState.cache ?? {}),
        },
        connection: {
          ...connectionReducer(undefined, { type: '@@INIT' }),
          ...(preloadedState.connection ?? {}),
        },
      }
    : undefined;

  return configureStore({
    reducer: {
      player: playerReducer,
      queue: queueReducer,
      cache: cacheReducer,
      connection: connectionReducer,
    },
    preloadedState: seededState,
    middleware: (getDefaultMiddleware) =>
      getDefaultMiddleware({
        serializableCheck: false, // Disable for tests to avoid warnings
      }),
  });
}

interface AllProvidersExtraProps {
  preloadedState?: PreloadedState;
  store?: ReturnType<typeof createTestStore>;
}

export function AllProviders({ children, preloadedState, store }: AllProvidersProps & AllProvidersExtraProps) {
  // Create a new QueryClient for each test to ensure isolation
  // Disable retries and refetching to make tests more predictable
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        staleTime: 0,
        refetchOnWindowFocus: false,
        refetchOnMount: false,
        refetchOnReconnect: false,
      },
      mutations: {
        retry: false,
      },
    },
  });

  // Create a fresh Redux store for each test (or reuse a caller-supplied
  // one) so behavior tests can observe `store.dispatch`/`store.getState`
  // and seed initial state via `preloadedState`.
  const testStore = store ?? createTestStore(preloadedState);

  // Note: DragDropContext removed to prevent "Should not already be working" errors
  // Tests that need drag-drop should wrap components individually with DragDropContext
  return (
    <ReduxProvider store={testStore}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ThemeProvider>
            <ToastProvider>
              {children}
            </ToastProvider>
          </ThemeProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </ReduxProvider>
  )
}

/**
 * Custom render function that wraps components with all providers.
 *
 * #3613: pass `preloadedState` to seed Redux for behavior tests, or
 * pass a `store` directly when the test needs to observe dispatches.
 * The returned object includes the active `store` for assertions.
 */
export type CustomRenderOptions = Omit<RenderOptions, 'wrapper'> & {
  preloadedState?: PreloadedState;
  store?: ReturnType<typeof createTestStore>;
};

export function customRender(
  ui: ReactElement,
  { preloadedState, store, ...options }: CustomRenderOptions = {},
) {
  const testStore = store ?? createTestStore(preloadedState);
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <AllProviders store={testStore}>{children}</AllProviders>
  );
  return { store: testStore, ...render(ui, { wrapper: Wrapper, ...options }) };
}

/**
 * Re-export everything from @testing-library/react
 */
export * from '@testing-library/react'

/**
 * Override the default render with our custom one
 */
export { customRender as render }
