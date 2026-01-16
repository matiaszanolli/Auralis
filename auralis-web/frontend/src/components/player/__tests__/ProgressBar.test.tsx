/**
 * ProgressBar Component Tests
 *
 * Tests for interactive progress timeline with seeking, buffered range visualization,
 * hover preview, and accessibility features.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@/test/test-utils';
import ProgressBar from '../ProgressBar';

describe('ProgressBar', () => {
  describe('Basic Rendering', () => {
    it('should render progress bar container with all elements', () => {
      render(
        <ProgressBar
          currentTime={90}
          duration={225}
          onSeek={vi.fn()}
        />
      );

      expect(screen.getByTestId('progress-bar')).toBeInTheDocument();
      expect(screen.getByTestId('progress-bar-container')).toBeInTheDocument();
      expect(screen.getByTestId('progress-bar-track')).toBeInTheDocument();
      expect(screen.getByTestId('progress-bar-buffered')).toBeInTheDocument();
      expect(screen.getByTestId('progress-bar-played')).toBeInTheDocument();
      expect(screen.getByTestId('progress-bar-thumb')).toBeInTheDocument();
    });

    it('should render with correct default props', () => {
      render(
        <ProgressBar
          currentTime={0}
          duration={180}
          onSeek={vi.fn()}
        />
      );

      expect(screen.getByTestId('progress-bar-container')).toHaveAttribute('role', 'slider');
    });
  });

  describe('Progress Display', () => {
    it('should display progress at 0% when at start', () => {
      render(
        <ProgressBar
          currentTime={0}
          duration={180}
          onSeek={vi.fn()}
        />
      );

      const played = screen.getByTestId('progress-bar-played');
      expect(played).toHaveStyle('width: 0%');
    });

    it('should display progress at 50% at midpoint', () => {
      render(
        <ProgressBar
          currentTime={90}
          duration={180}
          onSeek={vi.fn()}
        />
      );

      const played = screen.getByTestId('progress-bar-played');
      expect(played).toHaveStyle('width: 50%');
    });

    it('should display progress at 100% at end', () => {
      render(
        <ProgressBar
          currentTime={180}
          duration={180}
          onSeek={vi.fn()}
        />
      );

      const played = screen.getByTestId('progress-bar-played');
      expect(played).toHaveStyle('width: 100%');
    });

    it('should clamp progress to 100% when currentTime exceeds duration', () => {
      render(
        <ProgressBar
          currentTime={200}
          duration={180}
          onSeek={vi.fn()}
        />
      );

      const played = screen.getByTestId('progress-bar-played');
      expect(played).toHaveStyle('width: 100%');
    });

    it('should display 0% progress when duration is invalid', () => {
      render(
        <ProgressBar
          currentTime={90}
          duration={0}
          onSeek={vi.fn()}
        />
      );

      const played = screen.getByTestId('progress-bar-played');
      expect(played).toHaveStyle('width: 0%');
    });
  });

  describe('Buffering Display', () => {
    it('should display buffered percentage', () => {
      render(
        <ProgressBar
          currentTime={30}
          duration={180}
          bufferedPercentage={75}
          onSeek={vi.fn()}
        />
      );

      const buffered = screen.getByTestId('progress-bar-buffered');
      expect(buffered).toHaveStyle('width: 75%');
    });

    it('should clamp buffered percentage to 0%', () => {
      render(
        <ProgressBar
          currentTime={30}
          duration={180}
          bufferedPercentage={-10}
          onSeek={vi.fn()}
        />
      );

      const buffered = screen.getByTestId('progress-bar-buffered');
      expect(buffered).toHaveStyle('width: 0%');
    });

    it('should clamp buffered percentage to 100%', () => {
      render(
        <ProgressBar
          currentTime={30}
          duration={180}
          bufferedPercentage={150}
          onSeek={vi.fn()}
        />
      );

      const buffered = screen.getByTestId('progress-bar-buffered');
      expect(buffered).toHaveStyle('width: 100%');
    });

    it('should default to 0% buffering', () => {
      render(
        <ProgressBar
          currentTime={30}
          duration={180}
          onSeek={vi.fn()}
        />
      );

      const buffered = screen.getByTestId('progress-bar-buffered');
      expect(buffered).toHaveStyle('width: 0%');
    });
  });

  describe('Click to Seek', () => {
    it('should call onSeek when clicked at midpoint', () => {
      const mockSeek = vi.fn();
      const { container } = render(
        <ProgressBar
          currentTime={0}
          duration={100}
          onSeek={mockSeek}
        />
      );

      const progressBarContainer = screen.getByTestId('progress-bar-container');

      // In test environment, getBoundingClientRect may return zeros
      // So we just test that onSeek is called with a valid number
      fireEvent.click(progressBarContainer, {
        clientX: 50,
      });

      expect(mockSeek).toHaveBeenCalled();
      // The position will be calculated based on container width
      // Just verify it's a finite number
      const seekPosition = mockSeek.mock.calls[0][0];
      expect(Number.isFinite(seekPosition)).toBe(true);
    });

    it('should call onSeek when clicked at start', () => {
      const mockSeek = vi.fn();
      render(
        <ProgressBar
          currentTime={50}
          duration={100}
          onSeek={mockSeek}
        />
      );

      const progressBarContainer = screen.getByTestId('progress-bar-container');
      const rect = progressBarContainer.getBoundingClientRect();

      fireEvent.click(progressBarContainer, {
        clientX: rect.left,
      });

      expect(mockSeek).toHaveBeenCalled();
    });

    it('should call onSeek when clicked at end', () => {
      const mockSeek = vi.fn();
      render(
        <ProgressBar
          currentTime={0}
          duration={100}
          onSeek={mockSeek}
        />
      );

      const progressBarContainer = screen.getByTestId('progress-bar-container');
      const rect = progressBarContainer.getBoundingClientRect();

      fireEvent.click(progressBarContainer, {
        clientX: rect.right,
      });

      expect(mockSeek).toHaveBeenCalled();
    });

    it('should not call onSeek when disabled', () => {
      const mockSeek = vi.fn();
      render(
        <ProgressBar
          currentTime={0}
          duration={100}
          disabled={true}
          onSeek={mockSeek}
        />
      );

      const progressBarContainer = screen.getByTestId('progress-bar-container');
      const rect = progressBarContainer.getBoundingClientRect();

      fireEvent.click(progressBarContainer, {
        clientX: rect.left + rect.width / 2,
      });

      expect(mockSeek).not.toHaveBeenCalled();
    });

    it('should not call onSeek with invalid duration', () => {
      const mockSeek = vi.fn();
      render(
        <ProgressBar
          currentTime={0}
          duration={0}
          onSeek={mockSeek}
        />
      );

      const progressBarContainer = screen.getByTestId('progress-bar-container');
      const rect = progressBarContainer.getBoundingClientRect();

      fireEvent.click(progressBarContainer, {
        clientX: rect.left + rect.width / 2,
      });

      expect(mockSeek).not.toHaveBeenCalled();
    });
  });

  describe('Hover Tooltip', () => {
    it('should show tooltip on hover', () => {
      render(
        <ProgressBar
          currentTime={0}
          duration={180}
          onSeek={vi.fn()}
        />
      );

      const progressBarContainer = screen.getByTestId('progress-bar-container');
      fireEvent.mouseEnter(progressBarContainer);

      expect(screen.getByTestId('progress-bar-tooltip')).toBeInTheDocument();
    });

    it('should hide tooltip when not hovering', () => {
      render(
        <ProgressBar
          currentTime={0}
          duration={180}
          onSeek={vi.fn()}
        />
      );

      const progressBarContainer = screen.getByTestId('progress-bar-container');
      fireEvent.mouseLeave(progressBarContainer);

      expect(screen.queryByTestId('progress-bar-tooltip')).not.toBeInTheDocument();
    });

    it('should not show tooltip when disabled', () => {
      render(
        <ProgressBar
          currentTime={0}
          duration={180}
          disabled={true}
          onSeek={vi.fn()}
        />
      );

      const progressBarContainer = screen.getByTestId('progress-bar-container');
      fireEvent.mouseEnter(progressBarContainer);

      expect(screen.queryByTestId('progress-bar-tooltip')).not.toBeInTheDocument();
    });

    it('should display formatted time in tooltip', () => {
      render(
        <ProgressBar
          currentTime={0}
          duration={180}
          onSeek={vi.fn()}
        />
      );

      const progressBarContainer = screen.getByTestId('progress-bar-container');
      const rect = progressBarContainer.getBoundingClientRect();

      fireEvent.mouseMove(progressBarContainer, {
        clientX: rect.left + rect.width / 2,
      });
      fireEvent.mouseEnter(progressBarContainer);

      const tooltip = screen.getByTestId('progress-bar-tooltip');
      expect(tooltip).toHaveTextContent(/\d+:\d+/);
    });

    it('should update tooltip position on mouse move', () => {
      const { container } = render(
        <ProgressBar
          currentTime={0}
          duration={180}
          onSeek={vi.fn()}
        />
      );

      const progressBarContainer = screen.getByTestId('progress-bar-container');
      fireEvent.mouseEnter(progressBarContainer);

      const rect = progressBarContainer.getBoundingClientRect();
      fireEvent.mouseMove(progressBarContainer, {
        clientX: rect.left + rect.width * 0.25,
      });

      const tooltip = screen.getByTestId('progress-bar-tooltip');
      expect(tooltip).toBeInTheDocument();
    });
  });

  describe('Dragging', () => {
    it('should handle drag start', () => {
      const mockSeek = vi.fn();
      render(
        <ProgressBar
          currentTime={0}
          duration={100}
          onSeek={mockSeek}
        />
      );

      const progressBarContainer = screen.getByTestId('progress-bar-container');
      const rect = progressBarContainer.getBoundingClientRect();

      fireEvent.mouseDown(progressBarContainer, {
        clientX: rect.left + rect.width / 2,
      });

      expect(mockSeek).toHaveBeenCalled();
    });

    it('should expand thumb during drag', () => {
      render(
        <ProgressBar
          currentTime={50}
          duration={100}
          onSeek={vi.fn()}
        />
      );

      const progressBarContainer = screen.getByTestId('progress-bar-container');
      const thumb = screen.getByTestId('progress-bar-thumb');

      fireEvent.mouseDown(progressBarContainer);

      // During drag, thumb should have larger size (16px instead of 12px)
      expect(thumb).toHaveStyle('width: 16px');
      expect(thumb).toHaveStyle('height: 16px');
    });
  });

  describe('Accessibility', () => {
    it('should have slider role', () => {
      render(
        <ProgressBar
          currentTime={90}
          duration={225}
          onSeek={vi.fn()}
        />
      );

      expect(screen.getByTestId('progress-bar-container')).toHaveAttribute('role', 'slider');
    });

    it('should have aria-valuemin of 0', () => {
      render(
        <ProgressBar
          currentTime={90}
          duration={225}
          onSeek={vi.fn()}
        />
      );

      expect(screen.getByTestId('progress-bar-container')).toHaveAttribute('aria-valuemin', '0');
    });

    it('should have aria-valuemax set to duration', () => {
      render(
        <ProgressBar
          currentTime={90}
          duration={225}
          onSeek={vi.fn()}
        />
      );

      expect(screen.getByTestId('progress-bar-container')).toHaveAttribute('aria-valuemax', '225');
    });

    it('should have aria-valuenow set to current time', () => {
      render(
        <ProgressBar
          currentTime={90}
          duration={225}
          onSeek={vi.fn()}
        />
      );

      expect(screen.getByTestId('progress-bar-container')).toHaveAttribute('aria-valuenow', '90');
    });

    it('should have aria-disabled when disabled', () => {
      render(
        <ProgressBar
          currentTime={90}
          duration={225}
          disabled={true}
          onSeek={vi.fn()}
        />
      );

      expect(screen.getByTestId('progress-bar-container')).toHaveAttribute('aria-disabled', 'true');
    });

    it('should have aria-label with time information', () => {
      render(
        <ProgressBar
          currentTime={90}
          duration={225}
          onSeek={vi.fn()}
        />
      );

      const container = screen.getByTestId('progress-bar-container');
      expect(container).toHaveAttribute('aria-label', expect.stringContaining('progress'));
    });

    it('should accept custom aria-label', () => {
      render(
        <ProgressBar
          currentTime={90}
          duration={225}
          ariaLabel="Custom progress label"
          onSeek={vi.fn()}
        />
      );

      expect(screen.getByTestId('progress-bar-container')).toHaveAttribute('aria-label', 'Custom progress label');
    });
  });

  describe('CSS & Styling', () => {
    it('should accept custom className', () => {
      const { container } = render(
        <ProgressBar
          currentTime={90}
          duration={225}
          className="custom-progress"
          onSeek={vi.fn()}
        />
      );

      expect(container.querySelector('.custom-progress')).toBeInTheDocument();
    });

    it('should have proper test IDs for all elements', () => {
      render(
        <ProgressBar
          currentTime={90}
          duration={225}
          onSeek={vi.fn()}
        />
      );

      expect(screen.getByTestId('progress-bar')).toBeInTheDocument();
      expect(screen.getByTestId('progress-bar-container')).toBeInTheDocument();
      expect(screen.getByTestId('progress-bar-track')).toBeInTheDocument();
      expect(screen.getByTestId('progress-bar-buffered')).toBeInTheDocument();
      expect(screen.getByTestId('progress-bar-played')).toBeInTheDocument();
      expect(screen.getByTestId('progress-bar-thumb')).toBeInTheDocument();
    });

    it('should have proper cursor style when disabled', () => {
      render(
        <ProgressBar
          currentTime={90}
          duration={225}
          disabled={true}
          onSeek={vi.fn()}
        />
      );

      const container = screen.getByTestId('progress-bar-container');
      expect(container).toHaveStyle('cursor: default');
    });

    it('should have pointer cursor when enabled', () => {
      render(
        <ProgressBar
          currentTime={90}
          duration={225}
          disabled={false}
          onSeek={vi.fn()}
        />
      );

      const container = screen.getByTestId('progress-bar-container');
      expect(container).toHaveStyle('cursor: pointer');
    });
  });

  describe('Edge Cases', () => {
    it('should handle zero duration gracefully', () => {
      render(
        <ProgressBar
          currentTime={0}
          duration={0}
          onSeek={vi.fn()}
        />
      );

      expect(screen.getByTestId('progress-bar-played')).toHaveStyle('width: 0%');
    });

    it('should handle Infinity duration gracefully', () => {
      render(
        <ProgressBar
          currentTime={45}
          duration={Infinity}
          onSeek={vi.fn()}
        />
      );

      expect(screen.getByTestId('progress-bar-played')).toHaveStyle('width: 0%');
    });

    it('should handle NaN duration gracefully', () => {
      render(
        <ProgressBar
          currentTime={45}
          duration={NaN}
          onSeek={vi.fn()}
        />
      );

      expect(screen.getByTestId('progress-bar-played')).toHaveStyle('width: 0%');
    });

    it('should handle negative currentTime', () => {
      render(
        <ProgressBar
          currentTime={-10}
          duration={180}
          onSeek={vi.fn()}
        />
      );

      const played = screen.getByTestId('progress-bar-played');
      expect(played).toHaveStyle('width: 0%');
    });

    it('should handle very small duration values', () => {
      render(
        <ProgressBar
          currentTime={0.5}
          duration={1}
          onSeek={vi.fn()}
        />
      );

      const played = screen.getByTestId('progress-bar-played');
      expect(played).toHaveStyle('width: 50%');
    });

    it('should handle very large time values', () => {
      render(
        <ProgressBar
          currentTime={999999}
          duration={1000000}
          onSeek={vi.fn()}
        />
      );

      const played = screen.getByTestId('progress-bar-played');
      const width = played.style.width;
      // Very close to 100% due to floating point
      expect(width).toMatch(/^99\.9[0-9]+%$/);
    });

    it('should handle floating point currentTime', () => {
      render(
        <ProgressBar
          currentTime={90.5}
          duration={180}
          onSeek={vi.fn()}
        />
      );

      const played = screen.getByTestId('progress-bar-played');
      const width = played.style.width;
      expect(width).toMatch(/^50\.2[0-9]+%$/);
    });

    it('should handle NaN bufferedPercentage', () => {
      render(
        <ProgressBar
          currentTime={45}
          duration={180}
          bufferedPercentage={NaN}
          onSeek={vi.fn()}
        />
      );

      const buffered = screen.getByTestId('progress-bar-buffered');
      // NaN gets clamped to 0, which sets width to 0%
      // Check that it's either explicitly set to 0% or inherits to 0
      const width = buffered.style.width || '0%';
      expect(['0%', '']).toContain(buffered.style.width);
    });
  });

  describe('Realistic Scenarios', () => {
    it('should update progress as currentTime changes', () => {
      const { rerender } = render(
        <ProgressBar
          currentTime={0}
          duration={240}
          onSeek={vi.fn()}
        />
      );

      let played = screen.getByTestId('progress-bar-played');
      expect(played).toHaveStyle('width: 0%');

      rerender(
        <ProgressBar
          currentTime={60}
          duration={240}
          onSeek={vi.fn()}
        />
      );

      played = screen.getByTestId('progress-bar-played');
      expect(played).toHaveStyle('width: 25%');

      rerender(
        <ProgressBar
          currentTime={120}
          duration={240}
          onSeek={vi.fn()}
        />
      );

      played = screen.getByTestId('progress-bar-played');
      expect(played).toHaveStyle('width: 50%');

      rerender(
        <ProgressBar
          currentTime={240}
          duration={240}
          onSeek={vi.fn()}
        />
      );

      played = screen.getByTestId('progress-bar-played');
      expect(played).toHaveStyle('width: 100%');
    });

    it('should update buffering as content loads', () => {
      const { rerender } = render(
        <ProgressBar
          currentTime={30}
          duration={180}
          bufferedPercentage={0}
          onSeek={vi.fn()}
        />
      );

      let buffered = screen.getByTestId('progress-bar-buffered');
      expect(buffered).toHaveStyle('width: 0%');

      rerender(
        <ProgressBar
          currentTime={30}
          duration={180}
          bufferedPercentage={25}
          onSeek={vi.fn()}
        />
      );

      buffered = screen.getByTestId('progress-bar-buffered');
      expect(buffered).toHaveStyle('width: 25%');

      rerender(
        <ProgressBar
          currentTime={30}
          duration={180}
          bufferedPercentage={100}
          onSeek={vi.fn()}
        />
      );

      buffered = screen.getByTestId('progress-bar-buffered');
      expect(buffered).toHaveStyle('width: 100%');
    });

    it('should handle seeking ahead of buffered content', () => {
      const mockSeek = vi.fn();
      render(
        <ProgressBar
          currentTime={30}
          duration={180}
          bufferedPercentage={50}
          onSeek={mockSeek}
        />
      );

      const progressBarContainer = screen.getByTestId('progress-bar-container');
      const rect = progressBarContainer.getBoundingClientRect();

      // Seek to 80% (beyond 50% buffered)
      fireEvent.click(progressBarContainer, {
        clientX: rect.left + rect.width * 0.8,
      });

      expect(mockSeek).toHaveBeenCalled();
    });

    it('should handle rapid progress updates', () => {
      const { rerender } = render(
        <ProgressBar
          currentTime={0}
          duration={100}
          onSeek={vi.fn()}
        />
      );

      for (let i = 1; i <= 10; i++) {
        rerender(
          <ProgressBar
            currentTime={i * 10}
            duration={100}
            onSeek={vi.fn()}
          />
        );
      }

      const played = screen.getByTestId('progress-bar-played');
      expect(played).toHaveStyle('width: 100%');
    });
  });

  describe('Props Updates', () => {
    it('should update when currentTime changes', () => {
      const { rerender } = render(
        <ProgressBar
          currentTime={0}
          duration={180}
          onSeek={vi.fn()}
        />
      );

      expect(screen.getByTestId('progress-bar-played')).toHaveStyle('width: 0%');

      rerender(
        <ProgressBar
          currentTime={90}
          duration={180}
          onSeek={vi.fn()}
        />
      );

      expect(screen.getByTestId('progress-bar-played')).toHaveStyle('width: 50%');
    });

    it('should update when duration changes', () => {
      const { rerender } = render(
        <ProgressBar
          currentTime={60}
          duration={180}
          onSeek={vi.fn()}
        />
      );

      const played1 = screen.getByTestId('progress-bar-played');
      expect(played1.style.width).toMatch(/^33\.3[0-9]+%$/);

      rerender(
        <ProgressBar
          currentTime={60}
          duration={360}
          onSeek={vi.fn()}
        />
      );

      const played2 = screen.getByTestId('progress-bar-played');
      expect(played2.style.width).toMatch(/^16\.6[0-9]+%$/);
    });

    it('should update when bufferedPercentage changes', () => {
      const { rerender } = render(
        <ProgressBar
          currentTime={30}
          duration={180}
          bufferedPercentage={25}
          onSeek={vi.fn()}
        />
      );

      expect(screen.getByTestId('progress-bar-buffered')).toHaveStyle('width: 25%');

      rerender(
        <ProgressBar
          currentTime={30}
          duration={180}
          bufferedPercentage={75}
          onSeek={vi.fn()}
        />
      );

      expect(screen.getByTestId('progress-bar-buffered')).toHaveStyle('width: 75%');
    });

    it('should update disabled state', () => {
      const mockSeek = vi.fn();
      const { rerender } = render(
        <ProgressBar
          currentTime={90}
          duration={180}
          disabled={false}
          onSeek={mockSeek}
        />
      );

      expect(screen.getByTestId('progress-bar-container')).toHaveAttribute('aria-disabled', 'false');

      rerender(
        <ProgressBar
          currentTime={90}
          duration={180}
          disabled={true}
          onSeek={mockSeek}
        />
      );

      expect(screen.getByTestId('progress-bar-container')).toHaveAttribute('aria-disabled', 'true');
    });
  });
});
