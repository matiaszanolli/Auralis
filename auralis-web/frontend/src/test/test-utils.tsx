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
import { DragDropContext, DropResult } from '@hello-pangea/dnd'
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
  // Mock onDragEnd handler for DragDropContext
  const handleDragEnd = (_result: DropResult) => {
    // No-op in tests
  }

  return (
    <BrowserRouter>
      <DragDropContext onDragEnd={handleDragEnd}>
        <WebSocketProvider url="ws://localhost:8765/ws">
          <ThemeProvider>
            <EnhancementProvider>
              <ToastProvider>
                {children}
              </ToastProvider>
            </EnhancementProvider>
          </ThemeProvider>
        </WebSocketProvider>
      </DragDropContext>
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
