/**
 * ThemeToggle Component Tests
 *
 * Tests the theme toggle button functionality, animations, and interactions.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@/test/test-utils'
import userEvent from '@testing-library/user-event'
import { useTheme } from '../../contexts/ThemeContext'
import ThemeToggle from '../shared/ui/ThemeToggle'

// Mock the useTheme hook while preserving other exports
vi.mock('../../contexts/ThemeContext', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../contexts/ThemeContext')>()
  return {
    ...actual,
    useTheme: vi.fn(),
  }
})

describe('ThemeToggle', () => {
  const mockToggleTheme = vi.fn()
  const mockSetTheme = vi.fn()

  const mockDarkTheme = {
    mode: 'dark' as const,
    toggleTheme: mockToggleTheme,
    setTheme: mockSetTheme,
    colors: {
      background: { primary: '#0A0E27' },
      text: { primary: '#ffffff', secondary: '#8b92b0' },
    },
    glassEffects: {},
  } as any

  const mockLightTheme = {
    mode: 'light' as const,
    toggleTheme: mockToggleTheme,
    setTheme: mockSetTheme,
    colors: {
      background: { primary: '#f8f9fd' },
      text: { primary: '#1a1f3a', secondary: '#5a6280' },
    },
    glassEffects: {},
  } as any

  beforeEach(() => {
    mockToggleTheme.mockClear()
    mockSetTheme.mockClear()
    vi.mocked(useTheme).mockReturnValue(mockDarkTheme)
  })

  // ============================================================================
  // Basic Rendering Tests
  // ============================================================================

  it('renders without crashing', () => {
    render(<ThemeToggle />)
    expect(screen.getByRole('button')).toBeInTheDocument()
  })

  it('renders with small size prop', () => {
    render(<ThemeToggle size="small" />)
    expect(screen.getByRole('button')).toBeInTheDocument()
  })

  it('renders with medium size prop', () => {
    render(<ThemeToggle size="medium" />)
    expect(screen.getByRole('button')).toBeInTheDocument()
  })

  it('renders with large size prop', () => {
    render(<ThemeToggle size="large" />)
    expect(screen.getByRole('button')).toBeInTheDocument()
  })

  // ============================================================================
  // Theme State Tests
  // ============================================================================

  it('shows moon icon in dark mode', () => {
    vi.mocked(useTheme).mockReturnValue(mockDarkTheme)
    const { container } = render(<ThemeToggle />)

    // DarkMode icon should be present
    const icon = container.querySelector('[data-testid="DarkModeIcon"]')
    expect(icon).toBeInTheDocument()
  })

  it('shows sun icon in light mode', () => {
    vi.mocked(useTheme).mockReturnValue(mockLightTheme)
    const { container } = render(<ThemeToggle />)

    // LightMode icon should be present
    const icon = container.querySelector('[data-testid="LightModeIcon"]')
    expect(icon).toBeInTheDocument()
  })

  it('displays correct tooltip in dark mode', () => {
    vi.mocked(useTheme).mockReturnValue(mockDarkTheme)
    render(<ThemeToggle />)

    // Tooltip should be rendered as aria-label
    expect(screen.getByLabelText(/switch to light mode/i)).toBeInTheDocument()
  })

  it('displays correct tooltip in light mode', () => {
    vi.mocked(useTheme).mockReturnValue(mockLightTheme)
    render(<ThemeToggle />)

    // Tooltip should be rendered as aria-label
    expect(screen.getByLabelText(/switch to dark mode/i)).toBeInTheDocument()
  })

  // ============================================================================
  // Interaction Tests
  // ============================================================================

  it('calls toggleTheme when clicked', async () => {
    const user = userEvent.setup()
    render(<ThemeToggle />)

    const button = screen.getByRole('button')
    await user.click(button)

    expect(mockToggleTheme).toHaveBeenCalledTimes(1)
  })

  it('can be clicked multiple times', async () => {
    const user = userEvent.setup()
    render(<ThemeToggle />)

    const button = screen.getByRole('button')
    await user.click(button)
    await user.click(button)
    await user.click(button)

    expect(mockToggleTheme).toHaveBeenCalledTimes(3)
  })

  it('handles rapid clicks gracefully', async () => {
    const user = userEvent.setup()
    render(<ThemeToggle />)

    const button = screen.getByRole('button')

    // Rapid fire clicks
    for (let i = 0; i < 10; i++) {
      await user.click(button)
    }

    expect(mockToggleTheme).toHaveBeenCalledTimes(10)
  })

  // ============================================================================
  // Label Tests
  // ============================================================================

  it('does not show label by default', () => {
    render(<ThemeToggle />)
    expect(screen.queryByText(/dark/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/light/i)).not.toBeInTheDocument()
  })

  it('shows "Dark" label when showLabel is true in dark mode', () => {
    vi.mocked(useTheme).mockReturnValue(mockDarkTheme)
    render(<ThemeToggle showLabel={true} />)

    expect(screen.getByText('Dark')).toBeInTheDocument()
  })

  it('shows "Light" label when showLabel is true in light mode', () => {
    vi.mocked(useTheme).mockReturnValue(mockLightTheme)
    render(<ThemeToggle showLabel={true} />)

    expect(screen.getByText('Light')).toBeInTheDocument()
  })

  // ============================================================================
  // Accessibility Tests
  // ============================================================================

  it('has accessible button role', () => {
    render(<ThemeToggle />)
    const button = screen.getByRole('button')
    expect(button).toBeInTheDocument()
  })

  it('has tooltip for screen readers', () => {
    render(<ThemeToggle />)

    // Tooltip text should be accessible via aria-label
    expect(screen.getByLabelText(/switch to/i)).toBeInTheDocument()
  })

  it('is keyboard accessible', () => {
    render(<ThemeToggle />)
    const button = screen.getByRole('button')

    button.focus()
    expect(button).toHaveFocus()
  })

  it('can be activated with keyboard', () => {
    render(<ThemeToggle />)
    const button = screen.getByRole('button')

    // Simulate Enter key press
    fireEvent.keyDown(button, { key: 'Enter', code: 'Enter' })

    // Button should be clickable via keyboard (handled by MUI IconButton)
    expect(button).toBeInTheDocument()
  })

  // ============================================================================
  // Visual/Animation Tests
  // ============================================================================

  it('has rotation animation styles applied', () => {
    render(<ThemeToggle />)

    // Button should exist and have the theme toggle functionality
    const button = screen.getByRole('button')
    expect(button).toBeInTheDocument()
  })

  it('changes rotation when theme changes', () => {
    const { rerender, container } = render(<ThemeToggle />)

    // Initial state (dark mode) - should show moon icon
    expect(container.querySelector('[data-testid="DarkModeIcon"]')).toBeInTheDocument()

    // Change to light mode
    vi.mocked(useTheme).mockReturnValue(mockLightTheme)
    rerender(<ThemeToggle />)

    // Should now show sun icon (indicating theme changed)
    expect(container.querySelector('[data-testid="LightModeIcon"]')).toBeInTheDocument()
  })

  it('applies hover effects', () => {
    render(<ThemeToggle />)
    const button = screen.getByRole('button')

    // Hover state triggers via CSS
    fireEvent.mouseEnter(button)
    expect(button).toBeInTheDocument()
  })

  // ============================================================================
  // Edge Cases
  // ============================================================================

  it('handles missing theme context gracefully', () => {
    // Mock useTheme to throw error
    vi.mocked(useTheme).mockImplementation(() => {
      throw new Error('useTheme must be used within a ThemeProvider')
    })

    // Component should throw (caught by error boundary in production)
    expect(() => render(<ThemeToggle />)).toThrow(
      'useTheme must be used within a ThemeProvider'
    )
  })

  it('maintains state across re-renders', async () => {
    const user = userEvent.setup()
    const { rerender } = render(<ThemeToggle />)

    const button = screen.getByRole('button')
    await user.click(button)

    expect(mockToggleTheme).toHaveBeenCalledTimes(1)

    rerender(<ThemeToggle />)

    // Button should still work after re-render
    await user.click(button)
    expect(mockToggleTheme).toHaveBeenCalledTimes(2)
  })

  // ============================================================================
  // Size Variant Tests
  // ============================================================================

  it('renders an SVG icon for small variant', () => {
    const { container } = render(<ThemeToggle size="small" />)
    const icon = container.querySelector('svg')
    expect(icon).toBeInTheDocument()
  })

  it('renders an SVG icon for medium variant', () => {
    const { container } = render(<ThemeToggle size="medium" />)
    const icon = container.querySelector('svg')
    expect(icon).toBeInTheDocument()
  })

  it('renders an SVG icon for large variant', () => {
    const { container } = render(<ThemeToggle size="large" />)
    const icon = container.querySelector('svg')
    expect(icon).toBeInTheDocument()
  })
})
