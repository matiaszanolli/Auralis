/**
 * ShuffleModeSelector Component Tests
 *
 * Comprehensive test suite for shuffle mode selector.
 * Covers: rendering, mode selection, interactions
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ShuffleModeSelector } from '../ShuffleModeSelector';

describe('ShuffleModeSelector', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // =========================================================================
  // DISPLAY & LAYOUT
  // =========================================================================

  it('should render all shuffle modes', () => {
    const mockOnModeChange = vi.fn();
    render(
      <ShuffleModeSelector
        currentMode="random"
        onModeChange={mockOnModeChange}
      />
    );

    expect(screen.getByText('Random')).toBeInTheDocument();
    expect(screen.getByText('Weighted')).toBeInTheDocument();
    expect(screen.getByText('By Album')).toBeInTheDocument();
    expect(screen.getByText('By Artist')).toBeInTheDocument();
    expect(screen.getByText('Temporal')).toBeInTheDocument();
    expect(screen.getByText('No Repeat')).toBeInTheDocument();
  });

  it('should display shuffle mode icons', () => {
    const mockOnModeChange = vi.fn();
    render(
      <ShuffleModeSelector
        currentMode="random"
        onModeChange={mockOnModeChange}
      />
    );

    expect(screen.getByText('🔀')).toBeInTheDocument();
    expect(screen.getByText('⭐')).toBeInTheDocument();
    expect(screen.getByText('💿')).toBeInTheDocument();
    expect(screen.getByText('🎤')).toBeInTheDocument();
  });

  // =========================================================================
  // MODE SELECTION
  // =========================================================================

  it('should highlight current mode', () => {
    const mockOnModeChange = vi.fn();
    render(
      <ShuffleModeSelector
        currentMode="random"
        onModeChange={mockOnModeChange}
      />
    );

    const randomButton = screen.getByLabelText('Shuffle mode: Random');
    expect(randomButton).toHaveAttribute('aria-pressed', 'true');
  });

  it('should call onModeChange when mode is clicked', async () => {
    const mockOnModeChange = vi.fn();
    const user = userEvent.setup();

    render(
      <ShuffleModeSelector
        currentMode="random"
        onModeChange={mockOnModeChange}
      />
    );

    const albumButton = screen.getByLabelText('Shuffle mode: By Album');
    await user.click(albumButton);

    expect(mockOnModeChange).toHaveBeenCalledWith('album');
  });

  it('should switch between modes', async () => {
    const mockOnModeChange = vi.fn();
    const user = userEvent.setup();

    render(
      <ShuffleModeSelector
        currentMode="random"
        onModeChange={mockOnModeChange}
      />
    );

    const weightedButton = screen.getByLabelText('Shuffle mode: Weighted');
    await user.click(weightedButton);

    expect(mockOnModeChange).toHaveBeenCalledWith('weighted');

    const artistButton = screen.getByLabelText('Shuffle mode: By Artist');
    await user.click(artistButton);

    expect(mockOnModeChange).toHaveBeenCalledWith('artist');
  });

  // =========================================================================
  // DESCRIPTIONS & TOOLTIPS
  // =========================================================================

  it('should display mode descriptions on hover', async () => {
    const mockOnModeChange = vi.fn();
    const user = userEvent.setup();

    render(
      <ShuffleModeSelector
        currentMode="random"
        onModeChange={mockOnModeChange}
      />
    );

    const randomButton = screen.getByLabelText('Shuffle mode: Random');
    await user.hover(randomButton);

    // Should show tooltip with description
    expect(screen.getByText('Standard random shuffle')).toBeInTheDocument();
  });

  it('should show different descriptions for each mode', async () => {
    const mockOnModeChange = vi.fn();
    const user = userEvent.setup();

    render(
      <ShuffleModeSelector
        currentMode="random"
        onModeChange={mockOnModeChange}
      />
    );

    const albumButton = screen.getByLabelText('Shuffle mode: By Album');
    await user.hover(albumButton);

    expect(screen.getByText(/Keep album tracks together/)).toBeInTheDocument();
  });

  // =========================================================================
  // DISABLED STATE
  // =========================================================================

  it('should disable all buttons when disabled prop is true', () => {
    const mockOnModeChange = vi.fn();
    render(
      <ShuffleModeSelector
        currentMode="random"
        onModeChange={mockOnModeChange}
        disabled={true}
      />
    );

    const buttons = screen.getAllByRole('button');
    buttons.forEach((button) => {
      expect(button).toBeDisabled();
    });
  });

  it('should not call onModeChange when disabled', async () => {
    const mockOnModeChange = vi.fn();
    const user = userEvent.setup();

    render(
      <ShuffleModeSelector
        currentMode="random"
        onModeChange={mockOnModeChange}
        disabled={true}
      />
    );

    const albumButton = screen.getByLabelText('Shuffle mode: By Album');
    await user.click(albumButton);

    expect(mockOnModeChange).not.toHaveBeenCalled();
  });

  // =========================================================================
  // ACCESSIBILITY
  // =========================================================================

  it('should have proper ARIA labels', () => {
    const mockOnModeChange = vi.fn();
    render(
      <ShuffleModeSelector
        currentMode="random"
        onModeChange={mockOnModeChange}
      />
    );

    expect(screen.getByLabelText('Shuffle mode: Random')).toBeInTheDocument();
    expect(screen.getByLabelText('Shuffle mode: Weighted')).toBeInTheDocument();
    expect(screen.getByLabelText('Shuffle mode: By Album')).toBeInTheDocument();
  });

  it('should have aria-pressed attribute', () => {
    const mockOnModeChange = vi.fn();
    render(
      <ShuffleModeSelector
        currentMode="album"
        onModeChange={mockOnModeChange}
      />
    );

    const albumButton = screen.getByLabelText('Shuffle mode: By Album');
    expect(albumButton).toHaveAttribute('aria-pressed', 'true');

    const randomButton = screen.getByLabelText('Shuffle mode: Random');
    expect(randomButton).toHaveAttribute('aria-pressed', 'false');
  });

  it('should have title attributes for tooltips', () => {
    const mockOnModeChange = vi.fn();
    render(
      <ShuffleModeSelector
        currentMode="random"
        onModeChange={mockOnModeChange}
      />
    );

    const randomButton = screen.getByLabelText('Shuffle mode: Random');
    expect(randomButton).toHaveAttribute('title', 'Standard random shuffle');
  });

  // =========================================================================
  // KEYBOARD INTERACTION
  // =========================================================================

  it('should be keyboard accessible', async () => {
    const mockOnModeChange = vi.fn();
    const user = userEvent.setup();

    render(
      <ShuffleModeSelector
        currentMode="random"
        onModeChange={mockOnModeChange}
      />
    );

    const albumButton = screen.getByLabelText('Shuffle mode: By Album');
    albumButton.focus();

    await user.keyboard('{Enter}');

    expect(mockOnModeChange).toHaveBeenCalledWith('album');
  });

  // =========================================================================
  // CURRENT MODE CHANGES
  // =========================================================================

  it('should update active mode when currentMode prop changes', () => {
    const mockOnModeChange = vi.fn();
    const { rerender } = render(
      <ShuffleModeSelector
        currentMode="random"
        onModeChange={mockOnModeChange}
      />
    );

    expect(screen.getByLabelText('Shuffle mode: Random')).toHaveAttribute(
      'aria-pressed',
      'true'
    );

    rerender(
      <ShuffleModeSelector
        currentMode="album"
        onModeChange={mockOnModeChange}
      />
    );

    expect(screen.getByLabelText('Shuffle mode: By Album')).toHaveAttribute(
      'aria-pressed',
      'true'
    );
    expect(screen.getByLabelText('Shuffle mode: Random')).toHaveAttribute(
      'aria-pressed',
      'false'
    );
  });

  // =========================================================================
  // MULTIPLE CLICKS
  // =========================================================================

  it('should handle rapid mode changes', async () => {
    const mockOnModeChange = vi.fn();
    const user = userEvent.setup();

    render(
      <ShuffleModeSelector
        currentMode="random"
        onModeChange={mockOnModeChange}
      />
    );

    const randomButton = screen.getByLabelText('Shuffle mode: Random');
    const albumButton = screen.getByLabelText('Shuffle mode: By Album');
    const artistButton = screen.getByLabelText('Shuffle mode: By Artist');

    await user.click(albumButton);
    await user.click(artistButton);
    await user.click(randomButton);

    expect(mockOnModeChange).toHaveBeenCalledTimes(3);
  });
});
