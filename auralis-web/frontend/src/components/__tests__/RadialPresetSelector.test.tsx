/**
 * RadialPresetSelector Component Tests
 *
 * Tests the circular preset selector with all presets, interactions, and states.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, within } from '@/test/test-utils'
import RadialPresetSelector from '../RadialPresetSelector'

describe('RadialPresetSelector', () => {
  const mockOnPresetChange = vi.fn()

  const defaultProps = {
    currentPreset: 'adaptive',
    onPresetChange: mockOnPresetChange,
    disabled: false,
    size: 240,
  }

  beforeEach(() => {
    mockOnPresetChange.mockClear()
  })

  // ============================================================================
  // Basic Rendering Tests
  // ============================================================================

  it('renders without crashing', () => {
    render(<RadialPresetSelector {...defaultProps} />)
    expect(screen.getByText('ADAPTIVE')).toBeInTheDocument()
  })

  it('renders with correct size', () => {
    const { container } = render(<RadialPresetSelector {...defaultProps} size={300} />)
    const selector = container.firstChild
    expect(selector).toHaveStyle({ width: '300px', height: '300px' })
  })

  it('displays current preset in center hub', () => {
    render(<RadialPresetSelector {...defaultProps} currentPreset="warm" />)
    expect(screen.getByText('WARM')).toBeInTheDocument()
  })

  it('renders all 5 preset buttons', () => {
    render(<RadialPresetSelector {...defaultProps} />)

    // Check for all preset tooltips (they contain the full label)
    expect(screen.getByText('Adaptive')).toBeInTheDocument()
    expect(screen.getByText('Bright')).toBeInTheDocument()
    expect(screen.getByText('Punchy')).toBeInTheDocument()
    expect(screen.getByText('Warm')).toBeInTheDocument()
    expect(screen.getByText('Gentle')).toBeInTheDocument()
  })

  // ============================================================================
  // Interaction Tests
  // ============================================================================

  it('calls onPresetChange when clicking a different preset', () => {
    render(<RadialPresetSelector {...defaultProps} currentPreset="adaptive" />)

    // Find and click the Warm preset button
    const warmButton = screen.getByText('Warm').closest('div')?.parentElement
    if (warmButton) {
      fireEvent.click(warmButton)
    }

    expect(mockOnPresetChange).toHaveBeenCalledWith('warm')
    expect(mockOnPresetChange).toHaveBeenCalledTimes(1)
  })

  it('does not call onPresetChange when clicking current preset', () => {
    render(<RadialPresetSelector {...defaultProps} currentPreset="adaptive" />)

    // Click the already-active Adaptive preset
    const adaptiveButton = screen.getByText('Adaptive').closest('div')?.parentElement
    if (adaptiveButton) {
      fireEvent.click(adaptiveButton)
    }

    expect(mockOnPresetChange).not.toHaveBeenCalled()
  })

  it('shows hover state on mouse enter', () => {
    const { container } = render(<RadialPresetSelector {...defaultProps} />)

    // Find a preset button (not the current one)
    const warmButton = screen.getByText('Warm').closest('div')?.parentElement
    if (warmButton) {
      fireEvent.mouseEnter(warmButton)
      // Verify hover state is applied (component should handle this internally)
      expect(warmButton).toBeInTheDocument()
    }
  })

  // ============================================================================
  // Disabled State Tests
  // ============================================================================

  it('disables all interactions when disabled prop is true', () => {
    const { container } = render(
      <RadialPresetSelector {...defaultProps} disabled={true} />
    )

    // Component should have reduced opacity when disabled
    const selector = container.firstChild as HTMLElement
    expect(selector).toHaveStyle({ opacity: '0.4' })

    // Clicks should not trigger callback
    const warmButton = screen.getByText('Warm').closest('div')?.parentElement
    if (warmButton) {
      fireEvent.click(warmButton)
    }
    expect(mockOnPresetChange).not.toHaveBeenCalled()
  })

  it('has pointer-events: none when disabled', () => {
    const { container } = render(
      <RadialPresetSelector {...defaultProps} disabled={true} />
    )

    const selector = container.firstChild as HTMLElement
    expect(selector).toHaveStyle({ pointerEvents: 'none' })
  })

  // ============================================================================
  // Visual State Tests
  // ============================================================================

  it('applies active styling to current preset', () => {
    render(<RadialPresetSelector {...defaultProps} currentPreset="punchy" />)

    // Center hub should show the active preset
    expect(screen.getByText('PUNCHY')).toBeInTheDocument()
  })

  it('changes center hub when preset changes', () => {
    const { rerender } = render(
      <RadialPresetSelector {...defaultProps} currentPreset="adaptive" />
    )

    expect(screen.getByText('ADAPTIVE')).toBeInTheDocument()

    rerender(
      <RadialPresetSelector {...defaultProps} currentPreset="bright" />
    )

    expect(screen.getByText('BRIGHT')).toBeInTheDocument()
  })

  // ============================================================================
  // Tooltip Tests
  // ============================================================================

  it('displays preset description in tooltip on hover', () => {
    render(<RadialPresetSelector {...defaultProps} />)

    // Check that descriptions are accessible (in tooltips)
    expect(screen.getByText('Intelligent content-aware mastering')).toBeInTheDocument()
    expect(screen.getByText('Enhances clarity and presence')).toBeInTheDocument()
    expect(screen.getByText('Increases impact and dynamics')).toBeInTheDocument()
    expect(screen.getByText('Adds warmth and smoothness')).toBeInTheDocument()
    expect(screen.getByText('Subtle mastering with minimal processing')).toBeInTheDocument()
  })

  // ============================================================================
  // Icon Tests
  // ============================================================================

  it('renders correct icons for each preset', () => {
    const { container } = render(<RadialPresetSelector {...defaultProps} />)

    // Verify SVG icons are rendered (MUI icons render as SVG)
    const icons = container.querySelectorAll('svg')

    // Should have 5 preset icons + 1 center hub icon + SVG for connecting lines
    expect(icons.length).toBeGreaterThanOrEqual(6)
  })

  // ============================================================================
  // Accessibility Tests
  // ============================================================================

  it('has accessible tooltips with proper placement', () => {
    render(<RadialPresetSelector {...defaultProps} />)

    // Tooltips should be accessible
    const tooltips = screen.getAllByRole('tooltip', { hidden: true })
    expect(tooltips.length).toBeGreaterThan(0)
  })

  it('maintains keyboard accessibility structure', () => {
    const { container } = render(<RadialPresetSelector {...defaultProps} />)

    // Preset buttons should be clickable elements
    const clickableElements = container.querySelectorAll('[onClick]')
    expect(clickableElements.length).toBeGreaterThan(0)
  })

  // ============================================================================
  // Edge Cases
  // ============================================================================

  it('handles rapid preset changes', () => {
    render(<RadialPresetSelector {...defaultProps} currentPreset="adaptive" />)

    // Click multiple presets rapidly
    const warmButton = screen.getByText('Warm').closest('div')?.parentElement
    const brightButton = screen.getByText('Bright').closest('div')?.parentElement
    const punchyButton = screen.getByText('Punchy').closest('div')?.parentElement

    if (warmButton) fireEvent.click(warmButton)
    if (brightButton) fireEvent.click(brightButton)
    if (punchyButton) fireEvent.click(punchyButton)

    // Should have called onPresetChange for each click
    expect(mockOnPresetChange).toHaveBeenCalledTimes(3)
  })

  it('handles invalid preset gracefully', () => {
    // Should default to first preset if invalid preset is provided
    render(<RadialPresetSelector {...defaultProps} currentPreset="invalid-preset" as any />)

    // Should still render (falling back to adaptive)
    expect(screen.getByText('ADAPTIVE')).toBeInTheDocument()
  })

  // ============================================================================
  // Preset-Specific Tests
  // ============================================================================

  it('renders Adaptive preset correctly', () => {
    render(<RadialPresetSelector {...defaultProps} currentPreset="adaptive" />)
    expect(screen.getByText('ADAPTIVE')).toBeInTheDocument()
    expect(screen.getByText('Intelligent content-aware mastering')).toBeInTheDocument()
  })

  it('renders Bright preset correctly', () => {
    render(<RadialPresetSelector {...defaultProps} currentPreset="bright" />)
    expect(screen.getByText('BRIGHT')).toBeInTheDocument()
    expect(screen.getByText('Enhances clarity and presence')).toBeInTheDocument()
  })

  it('renders Punchy preset correctly', () => {
    render(<RadialPresetSelector {...defaultProps} currentPreset="punchy" />)
    expect(screen.getByText('PUNCHY')).toBeInTheDocument()
    expect(screen.getByText('Increases impact and dynamics')).toBeInTheDocument()
  })

  it('renders Warm preset correctly', () => {
    render(<RadialPresetSelector {...defaultProps} currentPreset="warm" />)
    expect(screen.getByText('WARM')).toBeInTheDocument()
    expect(screen.getByText('Adds warmth and smoothness')).toBeInTheDocument()
  })

  it('renders Gentle preset correctly', () => {
    render(<RadialPresetSelector {...defaultProps} currentPreset="gentle" />)
    expect(screen.getByText('GENTLE')).toBeInTheDocument()
    expect(screen.getByText('Subtle mastering with minimal processing')).toBeInTheDocument()
  })
})
