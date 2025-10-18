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
import { ThemeProvider } from '@mui/material/styles'
import { BrowserRouter } from 'react-router-dom'
import { auralisTheme } from '../theme/auralisTheme'

/**
 * Wrapper component that provides all necessary context providers
 */
interface AllProvidersProps {
  children: ReactNode
}

export function AllProviders({ children }: AllProvidersProps) {
  return (
    <BrowserRouter>
      <ThemeProvider theme={auralisTheme}>
        {children}
      </ThemeProvider>
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
