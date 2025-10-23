/**
 * Tests for GradientButton component
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@/test/test-utils'
import GradientButton from '../../components/shared/GradientButton'

describe('GradientButton', () => {
  it('renders with children text', () => {
    render(<GradientButton>Click Me</GradientButton>)
    expect(screen.getByText('Click Me')).toBeInTheDocument()
  })

  it('calls onClick handler when clicked', () => {
    const handleClick = vi.fn()
    render(<GradientButton onClick={handleClick}>Click Me</GradientButton>)

    const button = screen.getByText('Click Me')
    fireEvent.click(button)

    expect(handleClick).toHaveBeenCalledTimes(1)
  })

  it('is disabled when disabled prop is true', () => {
    const handleClick = vi.fn()
    render(
      <GradientButton onClick={handleClick} disabled>
        Click Me
      </GradientButton>
    )

    const button = screen.getByText('Click Me')
    fireEvent.click(button)

    // Click handler should not be called when disabled
    expect(handleClick).not.toHaveBeenCalled()
    expect(button).toBeDisabled()
  })

  it('renders with different sizes', () => {
    const { rerender } = render(
      <GradientButton size="small">Small</GradientButton>
    )
    expect(screen.getByText('Small')).toBeInTheDocument()

    rerender(<GradientButton size="medium">Medium</GradientButton>)
    expect(screen.getByText('Medium')).toBeInTheDocument()

    rerender(<GradientButton size="large">Large</GradientButton>)
    expect(screen.getByText('Large')).toBeInTheDocument()
  })

  it('renders with different variants', () => {
    const { rerender } = render(
      <GradientButton variant="contained">Contained</GradientButton>
    )
    expect(screen.getByText('Contained')).toBeInTheDocument()

    rerender(<GradientButton variant="outlined">Outlined</GradientButton>)
    expect(screen.getByText('Outlined')).toBeInTheDocument()

    rerender(<GradientButton variant="text">Text</GradientButton>)
    expect(screen.getByText('Text')).toBeInTheDocument()
  })

  it('applies fullWidth prop', () => {
    render(<GradientButton fullWidth>Full Width</GradientButton>)
    const button = screen.getByText('Full Width')
    expect(button).toHaveStyle({ width: '100%' })
  })

  it('renders with startIcon', () => {
    const icon = <span data-testid="start-icon">→</span>
    render(<GradientButton startIcon={icon}>With Icon</GradientButton>)

    expect(screen.getByTestId('start-icon')).toBeInTheDocument()
    expect(screen.getByText('With Icon')).toBeInTheDocument()
  })

  it('renders with endIcon', () => {
    const icon = <span data-testid="end-icon">←</span>
    render(<GradientButton endIcon={icon}>With Icon</GradientButton>)

    expect(screen.getByTestId('end-icon')).toBeInTheDocument()
    expect(screen.getByText('With Icon')).toBeInTheDocument()
  })

  it('applies custom className', () => {
    render(<GradientButton className="custom-class">Custom</GradientButton>)
    const button = screen.getByText('Custom')
    expect(button).toHaveClass('custom-class')
  })
})
