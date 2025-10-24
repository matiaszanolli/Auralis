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
import { ThemeProvider } from '../contexts/ThemeContext'
import { ToastProvider } from '../components/shared/Toast'
import { EnhancementProvider } from '../contexts/EnhancementContext'
import { WebSocketProvider } from '../contexts/WebSocketContext'

/**
 * Wrapper component that provides all necessary context providers
 */
interface AllProvidersProps {
  children: ReactNode
}

export function AllProviders({ children }: AllProvidersProps) {
  return (
    <BrowserRouter>
      <WebSocketProvider url="ws://localhost:8765/ws" autoConnect={false}>
        <ThemeProvider>
          <EnhancementProvider>
            <ToastProvider>
              {children}
            </ToastProvider>
          </EnhancementProvider>
        </ThemeProvider>
      </WebSocketProvider>
    </BrowserRouter>
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
