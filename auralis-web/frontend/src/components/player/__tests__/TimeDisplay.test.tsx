/**
 * TimeDisplay Component Tests
 *
 * Tests for time display formatting, live content detection,
 * accessibility, and edge cases.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@/test/test-utils';
import TimeDisplay from '../TimeDisplay';

describe('TimeDisplay', () => {
  describe('Basic Time Formatting', () => {
    it('should display current time and duration in mm:ss format', () => {
      render(
        <TimeDisplay
          currentTime={90}
          duration={225}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('1:30 / 3:45');
    });

    it('should display time with leading zeros for minutes under 10', () => {
      render(
        <TimeDisplay
          currentTime={45}
          duration={300}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('0:45 / 5:00');
    });

    it('should display zero time correctly', () => {
      render(
        <TimeDisplay
          currentTime={0}
          duration={180}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('0:00 / 3:00');
    });

    it('should display full duration correctly', () => {
      render(
        <TimeDisplay
          currentTime={180}
          duration={180}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('3:00 / 3:00');
    });
  });

  describe('Long Duration Formatting', () => {
    it('should display hours:minutes:seconds for durations >= 1 hour', () => {
      render(
        <TimeDisplay
          currentTime={3661}
          duration={7200}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('1:01:01 / 2:00:00');
    });

    it('should display hours even at 0 for long tracks', () => {
      render(
        <TimeDisplay
          currentTime={60}
          duration={7200}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('0:01:00 / 2:00:00');
    });

    it('should handle multiple hours correctly', () => {
      render(
        <TimeDisplay
          currentTime={36000}
          duration={43200}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('10:00:00 / 12:00:00');
    });
  });

  describe('Remaining Time Display', () => {
    it('should display remaining time when showRemaining is true', () => {
      render(
        <TimeDisplay
          currentTime={90}
          duration={225}
          showRemaining={true}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('1:30 / -2:15');
    });

    it('should show zero remaining when at end of track', () => {
      render(
        <TimeDisplay
          currentTime={180}
          duration={180}
          showRemaining={true}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('3:00 / -0:00');
    });

    it('should show remaining time with hours for long tracks', () => {
      render(
        <TimeDisplay
          currentTime={3661}
          duration={7200}
          showRemaining={true}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('1:01:01 / -0:58:59');
    });

    it('should handle remaining time at start of track', () => {
      render(
        <TimeDisplay
          currentTime={0}
          duration={300}
          showRemaining={true}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('0:00 / -5:00');
    });
  });

  describe('Live Content Detection', () => {
    it('should display LIVE for zero duration', () => {
      render(
        <TimeDisplay
          currentTime={45}
          duration={0}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('LIVE');
    });

    it('should display LIVE for Infinity duration', () => {
      render(
        <TimeDisplay
          currentTime={45}
          duration={Infinity}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('LIVE');
    });

    it('should display LIVE for NaN duration', () => {
      render(
        <TimeDisplay
          currentTime={45}
          duration={NaN}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('LIVE');
    });

    it('should ignore showRemaining for live content', () => {
      render(
        <TimeDisplay
          currentTime={45}
          duration={0}
          showRemaining={true}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('LIVE');
      expect(screen.getByTestId('time-display')).not.toHaveTextContent('-');
    });
  });

  describe('Accessibility', () => {
    it('should have proper aria-label for duration display', () => {
      render(
        <TimeDisplay
          currentTime={90}
          duration={225}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveAttribute(
        'aria-label',
        expect.stringContaining('Duration')
      );
    });

    it('should have proper aria-label for remaining time display', () => {
      render(
        <TimeDisplay
          currentTime={90}
          duration={225}
          showRemaining={true}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveAttribute(
        'aria-label',
        expect.stringContaining('Time remaining')
      );
    });

    it('should have proper aria-label for live content', () => {
      render(
        <TimeDisplay
          currentTime={45}
          duration={0}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveAttribute(
        'aria-label',
        'Live stream'
      );
    });

    it('should accept custom aria-label', () => {
      render(
        <TimeDisplay
          currentTime={90}
          duration={225}
          ariaLabel="Custom time label"
        />
      );

      expect(screen.getByTestId('time-display')).toHaveAttribute(
        'aria-label',
        'Custom time label'
      );
    });

    it('should use time element for semantic HTML', () => {
      const { container } = render(
        <TimeDisplay
          currentTime={90}
          duration={225}
        />
      );

      expect(container.querySelector('time')).toBeInTheDocument();
    });
  });

  describe('CSS Classes and Styling', () => {
    it('should accept custom className', () => {
      const { container } = render(
        <TimeDisplay
          currentTime={90}
          duration={225}
          className="custom-time-display"
        />
      );

      expect(container.querySelector('.custom-time-display')).toBeInTheDocument();
    });

    it('should have data-testid for testing', () => {
      render(
        <TimeDisplay
          currentTime={90}
          duration={225}
        />
      );

      expect(screen.getByTestId('time-display')).toBeInTheDocument();
    });

    it('should have title attribute for tooltip', () => {
      render(
        <TimeDisplay
          currentTime={90}
          duration={225}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveAttribute(
        'title',
        '1:30 / 3:45'
      );
    });
  });

  describe('Edge Cases', () => {
    it('should handle negative currentTime gracefully', () => {
      render(
        <TimeDisplay
          currentTime={-10}
          duration={180}
        />
      );

      // Should display 0:00 for negative values
      expect(screen.getByTestId('time-display')).toHaveTextContent('0:00 / 3:00');
    });

    it('should handle currentTime exceeding duration', () => {
      render(
        <TimeDisplay
          currentTime={200}
          duration={180}
        />
      );

      // Should display over 100% time
      expect(screen.getByTestId('time-display')).toHaveTextContent('3:20 / 3:00');
    });

    it('should handle very small duration values', () => {
      render(
        <TimeDisplay
          currentTime={0.5}
          duration={1}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('0:00 / 0:01');
    });

    it('should handle very large time values', () => {
      render(
        <TimeDisplay
          currentTime={999999}
          duration={1000000}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('277:46:39 / 277:46:40');
    });

    it('should handle floating point currentTime', () => {
      render(
        <TimeDisplay
          currentTime={90.5}
          duration={225}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('1:30');
    });

    it('should handle floating point duration', () => {
      render(
        <TimeDisplay
          currentTime={90}
          duration={225.9}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('3:45');
    });

    it('should handle both zero currentTime and duration', () => {
      render(
        <TimeDisplay
          currentTime={0}
          duration={0}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('LIVE');
    });
  });

  describe('Realistic Scenarios', () => {
    it('should display progression through a track', () => {
      const { rerender } = render(
        <TimeDisplay
          currentTime={0}
          duration={240}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('0:00 / 4:00');

      rerender(
        <TimeDisplay
          currentTime={60}
          duration={240}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('1:00 / 4:00');

      rerender(
        <TimeDisplay
          currentTime={120}
          duration={240}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('2:00 / 4:00');

      rerender(
        <TimeDisplay
          currentTime={240}
          duration={240}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('4:00 / 4:00');
    });

    it('should toggle between duration and remaining time', () => {
      const { rerender } = render(
        <TimeDisplay
          currentTime={60}
          duration={180}
          showRemaining={false}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('1:00 / 3:00');

      rerender(
        <TimeDisplay
          currentTime={60}
          duration={180}
          showRemaining={true}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('1:00 / -2:00');
    });

    it('should handle album-length tracks with hours', () => {
      render(
        <TimeDisplay
          currentTime={1234}
          duration={5400}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('0:20:34 / 1:30:00');
    });

    it('should maintain format consistency when paused and playing', () => {
      const { rerender } = render(
        <TimeDisplay
          currentTime={90}
          duration={225}
        />
      );

      screen.getByTestId('time-display').textContent;

      rerender(
        <TimeDisplay
          currentTime={91}
          duration={225}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('1:31 / 3:45');
    });
  });

  describe('Props Updates', () => {
    it('should update display when currentTime changes', () => {
      const { rerender } = render(
        <TimeDisplay
          currentTime={30}
          duration={180}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('0:30 / 3:00');

      rerender(
        <TimeDisplay
          currentTime={60}
          duration={180}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('1:00 / 3:00');
    });

    it('should update display when duration changes', () => {
      const { rerender } = render(
        <TimeDisplay
          currentTime={60}
          duration={180}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('1:00 / 3:00');

      rerender(
        <TimeDisplay
          currentTime={60}
          duration={360}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('1:00 / 6:00');
    });

    it('should update format when duration crosses hour threshold', () => {
      const { rerender } = render(
        <TimeDisplay
          currentTime={60}
          duration={3600}
        />
      );

      // With h:mm:ss format for durations >= 3600
      expect(screen.getByTestId('time-display')).toHaveTextContent('0:01:00 / 1:00:00');

      rerender(
        <TimeDisplay
          currentTime={60}
          duration={180}
        />
      );

      // Without h:mm:ss format for durations < 3600
      expect(screen.getByTestId('time-display')).toHaveTextContent('1:00 / 3:00');
    });

    it('should update aria-label when showRemaining changes', () => {
      const { rerender } = render(
        <TimeDisplay
          currentTime={60}
          duration={180}
          showRemaining={false}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveAttribute(
        'aria-label',
        expect.stringContaining('Duration')
      );

      rerender(
        <TimeDisplay
          currentTime={60}
          duration={180}
          showRemaining={true}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveAttribute(
        'aria-label',
        expect.stringContaining('Time remaining')
      );
    });
  });

  describe('Memoization Performance', () => {
    it('should not recalculate format on same props', () => {
      const { rerender } = render(
        <TimeDisplay
          currentTime={90}
          duration={225}
        />
      );

      const firstText = screen.getByTestId('time-display').textContent;

      rerender(
        <TimeDisplay
          currentTime={90}
          duration={225}
        />
      );

      expect(screen.getByTestId('time-display').textContent).toBe(firstText);
    });

    it('should recalculate only when relevant props change', () => {
      const { rerender } = render(
        <TimeDisplay
          currentTime={90}
          duration={225}
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('1:30 / 3:45');

      rerender(
        <TimeDisplay
          currentTime={90}
          duration={225}
          className="new-class"
        />
      );

      expect(screen.getByTestId('time-display')).toHaveTextContent('1:30 / 3:45');
    });
  });
});
