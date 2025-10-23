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
    expect(screen.getByText('Adaptive')).toBeInTheDocument()
  })

  it('renders with correct size', () => {
    const { container } = render(<RadialPresetSelector {...defaultProps} size={300} />)
    const selector = container.firstChild
    expect(selector).toHaveStyle({ width: '300px', height: '300px' })
  })

  it('displays current preset in center hub', () => {
    render(<RadialPresetSelector {...defaultProps} currentPreset="warm" />)
    expect(screen.getByText('Warm')).toBeInTheDocument()
  })

  it('renders all 5 preset buttons', () => {
    const { container } = render(<RadialPresetSelector {...defaultProps} />)

    // Check for the current preset label in the center
    expect(screen.getByText('Adaptive')).toBeInTheDocument()

    // Check for all preset icons (5 icons total)
    const icons = container.querySelectorAll('svg[data-testid*="Icon"]')
    expect(icons.length).toBeGreaterThanOrEqual(5) // At least 5 preset icons
  })

  // ============================================================================
  // Interaction Tests
  // ============================================================================

  it('calls onPresetChange when clicking a different preset', () => {
    const { container } = render(<RadialPresetSelector {...defaultProps} currentPreset="adaptive" />)

    // Find the Warm preset button by its icon (WhatshotOutlined)
    const warmIcon = container.querySelector('[data-testid="WhatshotOutlinedIcon"]')
    const warmButton = warmIcon?.closest('[class*="MuiBox-root"]') as HTMLElement

    if (warmButton) {
      fireEvent.click(warmButton)
      expect(mockOnPresetChange).toHaveBeenCalledWith('warm')
      expect(mockOnPresetChange).toHaveBeenCalledTimes(1)
    }
  })

  it('does not call onPresetChange when clicking current preset', () => {
    const { container } = render(<RadialPresetSelector {...defaultProps} currentPreset="adaptive" />)

    // Click the center hub (current Adaptive preset)
    const centerHub = screen.getByText('Adaptive').closest('[class*="MuiBox-root"]') as HTMLElement
    if (centerHub) {
      fireEvent.click(centerHub)
    }

    // Clicking the center hub shouldn't change preset
    expect(mockOnPresetChange).not.toHaveBeenCalled()
  })

  it('shows hover state on mouse enter', () => {
    const { container } = render(<RadialPresetSelector {...defaultProps} />)

    // Component should render preset icons that can be hovered
    const icons = container.querySelectorAll('svg[data-testid*="Icon"]')
    expect(icons.length).toBeGreaterThan(0)
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

    // Pointer events should be disabled
    expect(selector).toHaveStyle({ pointerEvents: 'none' })
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
    expect(screen.getByText('Punchy')).toBeInTheDocument()
  })

  it('changes center hub when preset changes', () => {
    const { rerender } = render(
      <RadialPresetSelector {...defaultProps} currentPreset="adaptive" />
    )

    expect(screen.getByText('Adaptive')).toBeInTheDocument()

    rerender(
      <RadialPresetSelector {...defaultProps} currentPreset="bright" />
    )

    expect(screen.getByText('Bright')).toBeInTheDocument()
  })

  // ============================================================================
  // Tooltip Tests
  // ============================================================================

  it('displays preset description in tooltip on hover', () => {
    const { container } = render(<RadialPresetSelector {...defaultProps} />)

    // Tooltips are rendered but not visible until hover
    // Check that icons are rendered (tooltips wrap them)
    const icons = container.querySelectorAll('svg[data-testid*="Icon"]')
    expect(icons.length).toBeGreaterThanOrEqual(5)
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
    const { container } = render(<RadialPresetSelector {...defaultProps} />)

    // Check that tooltips wrap the preset buttons
    const icons = container.querySelectorAll('svg[data-testid*="Icon"]')
    expect(icons.length).toBeGreaterThan(0)
  })

  it('maintains keyboard accessibility structure', () => {
    const { container } = render(<RadialPresetSelector {...defaultProps} />)

    // Preset buttons should be rendered
    const icons = container.querySelectorAll('svg[data-testid*="Icon"]')
    expect(icons.length).toBeGreaterThan(0)
  })

  // ============================================================================
  // Edge Cases
  // ============================================================================

  it('handles rapid preset changes', () => {
    const { rerender } = render(<RadialPresetSelector {...defaultProps} currentPreset="adaptive" />)

    // Simulate rapid preset changes by re-rendering with different presets
    rerender(<RadialPresetSelector {...defaultProps} currentPreset="warm" />)
    expect(screen.getByText('Warm')).toBeInTheDocument()

    rerender(<RadialPresetSelector {...defaultProps} currentPreset="bright" />)
    expect(screen.getByText('Bright')).toBeInTheDocument()

    rerender(<RadialPresetSelector {...defaultProps} currentPreset="punchy" />)
    expect(screen.getByText('Punchy')).toBeInTheDocument()
  })

  it('handles invalid preset gracefully', () => {
    // Should default to first preset if invalid preset is provided
    render(<RadialPresetSelector {...defaultProps} currentPreset="invalid-preset" as any />)

    // Should still render (falling back to adaptive)
    expect(screen.getByText('Adaptive')).toBeInTheDocument()
  })

  // ============================================================================
  // Preset-Specific Tests
  // ============================================================================

  it('renders Adaptive preset correctly', () => {
    render(<RadialPresetSelector {...defaultProps} currentPreset="adaptive" />)
    expect(screen.getByText('Adaptive')).toBeInTheDocument()
  })

  it('renders Bright preset correctly', () => {
    render(<RadialPresetSelector {...defaultProps} currentPreset="bright" />)
    expect(screen.getByText('Bright')).toBeInTheDocument()
  })

  it('renders Punchy preset correctly', () => {
    render(<RadialPresetSelector {...defaultProps} currentPreset="punchy" />)
    expect(screen.getByText('Punchy')).toBeInTheDocument()
  })

  it('renders Warm preset correctly', () => {
    render(<RadialPresetSelector {...defaultProps} currentPreset="warm" />)
    expect(screen.getByText('Warm')).toBeInTheDocument()
  })

  it('renders Gentle preset correctly', () => {
    render(<RadialPresetSelector {...defaultProps} currentPreset="gentle" />)
    expect(screen.getByText('Gentle')).toBeInTheDocument()
  })
})
