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

import React, { ReactElement, ReactNode, createContext, useContext } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from '../contexts/ThemeContext'
import { ToastProvider } from '../components/shared/Toast'

/**
 * Mock WebSocket Context for Testing
 * Provides the same interface as WebSocketContext but without real connections.
 * This prevents "Should not already be working" errors caused by WebSocket
 * singleton state persisting across tests.
 */
interface MockWebSocketContextValue {
  isConnected: boolean;
  connectionStatus: 'connected' | 'connecting' | 'disconnected' | 'error';
  subscribe: (messageType: string, handler: (message: any) => void) => () => void;
  subscribeAll: (handler: (message: any) => void) => () => void;
  send: (message: any) => void;
  connect: () => void;
  disconnect: () => void;
}

const MockWebSocketContext = createContext<MockWebSocketContextValue>({
  isConnected: true,
  connectionStatus: 'connected',
  subscribe: () => () => {},
  subscribeAll: () => () => {},
  send: () => {},
  connect: () => {},
  disconnect: () => {},
});

function MockWebSocketProvider({ children }: { children: ReactNode }) {
  const value: MockWebSocketContextValue = {
    isConnected: true,
    connectionStatus: 'connected',
    subscribe: () => () => {},
    subscribeAll: () => () => {},
    send: () => {},
    connect: () => {},
    disconnect: () => {},
  };

  return (
    <MockWebSocketContext.Provider value={value}>
      {children}
    </MockWebSocketContext.Provider>
  );
}

// Export mock context hook for tests that need to access it
export const useWebSocketContext = () => useContext(MockWebSocketContext);

/**
 * Mock Enhancement Context for Testing
 * Provides a simple implementation without WebSocket dependencies.
 */
interface MockEnhancementContextValue {
  settings: {
    enabled: boolean;
    preset: string;
    intensity: number;
  };
  setEnabled: (enabled: boolean) => void;
  setPreset: (preset: string) => void;
  setIntensity: (intensity: number) => void;
  isProcessing: boolean;
}

const MockEnhancementContext = createContext<MockEnhancementContextValue>({
  settings: { enabled: true, preset: 'adaptive', intensity: 1.0 },
  setEnabled: () => {},
  setPreset: () => {},
  setIntensity: () => {},
  isProcessing: false,
});

function MockEnhancementProvider({ children }: { children: ReactNode }) {
  const value: MockEnhancementContextValue = {
    settings: { enabled: true, preset: 'adaptive', intensity: 1.0 },
    setEnabled: () => {},
    setPreset: () => {},
    setIntensity: () => {},
    isProcessing: false,
  };

  return (
    <MockEnhancementContext.Provider value={value}>
      {children}
    </MockEnhancementContext.Provider>
  );
}

// Export mock enhancement hook for tests
export const useEnhancement = () => useContext(MockEnhancementContext);

/**
 * Wrapper component that provides all necessary context providers
 * Uses MOCK providers to avoid WebSocket singleton issues in tests
 */
interface AllProvidersProps {
  children: ReactNode
}

export function AllProviders({ children }: AllProvidersProps) {
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

  // Note: DragDropContext removed to prevent "Should not already be working" errors
  // Tests that need drag-drop should wrap components individually with DragDropContext
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <MockWebSocketProvider>
          <ThemeProvider>
            <MockEnhancementProvider>
              <ToastProvider>
                {children}
              </ToastProvider>
            </MockEnhancementProvider>
          </ThemeProvider>
        </MockWebSocketProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

/**
 * Custom render function that wraps components with all providers
 */
export function customRender(
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) {
  return render(ui, { wrapper: AllProviders, ...options })
}

/**
 * Re-export everything from @testing-library/react
 */
export * from '@testing-library/react'

/**
 * Override the default render with our custom one
 */
export { customRender as render }
