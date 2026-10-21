/**
 * ProgressBar Component Tests
 *
 * Tests for interactive progress timeline with seeking, buffered range visualization,
 * hover preview, and accessibility features.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
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
    it('should call onSeek when clicked at midpoint', async () => {
      const user = userEvent.setup();
      const mockSeek = vi.fn();
      render(
        <ProgressBar
          currentTime={0}
          duration={100}
          onSeek={mockSeek}
        />
      );

      const progressBarContainer = screen.getByTestId('progress-bar-container');

      // In test environment, getBoundingClientRect may return zeros
      // So we just test that onSeek is called with a valid number
      await user.click(progressBarContainer);

      expect(mockSeek).toHaveBeenCalled();
      // The position will be calculated based on container width
      // Just verify it's a finite number
      const seekPosition = mockSeek.mock.calls[0][0];
      expect(Number.isFinite(seekPosition)).toBe(true);
    });

    it('should call onSeek when clicked at start', async () => {
      const user = userEvent.setup();
      const mockSeek = vi.fn();
      render(
        <ProgressBar
          currentTime={50}
          duration={100}
          onSeek={mockSeek}
        />
      );

      const progressBarContainer = screen.getByTestId('progress-bar-container');

      await user.click(progressBarContainer);

      expect(mockSeek).toHaveBeenCalled();
    });

    it('should call onSeek when clicked at end', async () => {
      const user = userEvent.setup();
      const mockSeek = vi.fn();
      render(
        <ProgressBar
          currentTime={0}
          duration={100}
          onSeek={mockSeek}
        />
      );

      const progressBarContainer = screen.getByTestId('progress-bar-container');

      await user.click(progressBarContainer);

      expect(mockSeek).toHaveBeenCalled();
    });

    it('should not call onSeek when disabled', async () => {
      const user = userEvent.setup();
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

      await user.click(progressBarContainer);

      expect(mockSeek).not.toHaveBeenCalled();
    });

    it('should not call onSeek with invalid duration', async () => {
      const user = userEvent.setup();
      const mockSeek = vi.fn();
      render(
        <ProgressBar
          currentTime={0}
          duration={0}
          onSeek={mockSeek}
        />
      );

      const progressBarContainer = screen.getByTestId('progress-bar-container');

      await user.click(progressBarContainer);

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
      render(
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
    // jsdom rects are all zeros; a measurable bar makes the drag positions
    // exact (clientX 90 on a 100px bar at duration 100 → position 90).
    const measureBar = (element: Element) => {
      vi.spyOn(element, 'getBoundingClientRect').mockReturnValue({
        width: 100,
        height: 12,
        left: 0,
        top: 0,
        right: 100,
        bottom: 12,
        x: 0,
        y: 0,
        toJSON: () => ({}),
      } as DOMRect);
    };

    const renderBar = (mockSeek = vi.fn()) => {
      const utils = render(
        <ProgressBar currentTime={0} duration={100} onSeek={mockSeek} />
      );
      const bar = screen.getByTestId('progress-bar-container');
      measureBar(bar);
      return { mockSeek, bar, ...utils };
    };

    it('should handle drag start', () => {
      // #5625: mousedown no longer seeks — it only starts the gesture. The
      // old behavior fired a stream-restarting seek on mousedown, again on
      // every mousemove, and a third time on the trailing click.
      const { mockSeek, bar } = renderBar();

      fireEvent.mouseDown(bar, { clientX: 50 });

      expect(mockSeek).not.toHaveBeenCalled();
    });

    it('commits exactly one seek on release, at the last dragged position', () => {
      const { mockSeek, bar } = renderBar();

      fireEvent.mouseDown(bar, { clientX: 10 });
      fireEvent.mouseMove(document, { clientX: 40 });
      fireEvent.mouseMove(document, { clientX: 65 });
      fireEvent.mouseMove(document, { clientX: 90 });
      fireEvent.mouseUp(document);

      expect(mockSeek).toHaveBeenCalledTimes(1);
      expect(mockSeek).toHaveBeenCalledWith(90);
    });

    it('a plain click still seeks once', () => {
      const { mockSeek, bar } = renderBar();

      fireEvent.mouseDown(bar, { clientX: 30 });
      fireEvent.mouseUp(document);
      fireEvent.click(bar, { clientX: 30 });

      expect(mockSeek).toHaveBeenCalledTimes(1);
      expect(mockSeek).toHaveBeenCalledWith(30);
    });

    it('the trailing click after a drag does not seek again', () => {
      const { mockSeek, bar } = renderBar();

      fireEvent.mouseDown(bar, { clientX: 10 });
      fireEvent.mouseMove(document, { clientX: 90 });
      fireEvent.mouseUp(document);
      // Browsers dispatch click on the container after mouseup.
      fireEvent.click(bar, { clientX: 90 });

      expect(mockSeek).toHaveBeenCalledTimes(1);
    });

    it('updates the visual position during the drag without seeking', () => {
      const { bar } = renderBar();

      fireEvent.mouseDown(bar, { clientX: 10 });
      fireEvent.mouseMove(document, { clientX: 75 });

      // The played range follows the pointer while the seek is still pending.
      expect(screen.getByTestId('progress-bar-played')).toHaveStyle('width: 75%');
      expect(screen.queryByTestId('region-error-fallback')).toBeNull();
    });

    it('touch drag commits one seek on touchend at the last position', () => {
      const { mockSeek, bar } = renderBar();

      fireEvent.touchStart(bar, { touches: [{ clientX: 10 }] });
      fireEvent.touchMove(bar, { touches: [{ clientX: 45 }] });
      fireEvent.touchMove(bar, { touches: [{ clientX: 80 }] });
      fireEvent.touchEnd(bar);

      expect(mockSeek).toHaveBeenCalledTimes(1);
      expect(mockSeek).toHaveBeenCalledWith(80);

      // The synthetic click some browsers fire after a moved touch must not
      // seek a second time.
      fireEvent.click(bar, { clientX: 80 });
      expect(mockSeek).toHaveBeenCalledTimes(1);
    });

    it('a touch tap seeks once even if no synthetic click arrives', () => {
      const { mockSeek, bar } = renderBar();

      fireEvent.touchStart(bar, { touches: [{ clientX: 42 }] });
      fireEvent.touchEnd(bar);

      expect(mockSeek).toHaveBeenCalledTimes(1);
      expect(mockSeek).toHaveBeenCalledWith(42);
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

    it('should handle seeking ahead of buffered content', async () => {
      const user = userEvent.setup();
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

      // Seek beyond 50% buffered
      await user.click(progressBarContainer);

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
