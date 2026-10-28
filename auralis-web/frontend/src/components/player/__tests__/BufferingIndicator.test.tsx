/**
 * BufferingIndicator Component Tests
 *
 * Tests for buffering progress visualization, status states, and accessibility.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@/test/test-utils';
import BufferingIndicator from '../BufferingIndicator';

describe('BufferingIndicator', () => {
  describe('Basic Rendering', () => {
    it('should display buffered percentage in progress bar', () => {
      render(
        <BufferingIndicator
          bufferedPercentage={75}
          isBuffering={false}
        />
      );

      const bar = screen.getByTestId('buffered-bar');
      expect(bar).toHaveStyle('width: 75%');
      expect(screen.getByTestId('buffered-percentage')).toHaveTextContent('75%');
    });

    it('should display zero percent correctly', () => {
      render(
        <BufferingIndicator
          bufferedPercentage={0}
          isBuffering={false}
        />
      );

      expect(screen.getByTestId('buffered-percentage')).toHaveTextContent('0%');
      expect(screen.getByTestId('buffered-bar')).toHaveStyle('width: 0%');
    });

    it('should display 100 percent correctly', () => {
      render(
        <BufferingIndicator
          bufferedPercentage={100}
          isBuffering={false}
        />
      );

      expect(screen.getByTestId('buffered-percentage')).toHaveTextContent('100%');
      expect(screen.getByTestId('buffered-bar')).toHaveStyle('width: 100%');
    });

    it('should round floating point percentages', () => {
      render(
        <BufferingIndicator
          bufferedPercentage={75.6}
          isBuffering={false}
        />
      );

      expect(screen.getByTestId('buffered-percentage')).toHaveTextContent('76%');
    });
  });

  describe('Buffering State', () => {
    it('should display spinner when buffering', () => {
      render(
        <BufferingIndicator
          bufferedPercentage={25}
          isBuffering={true}
        />
      );

      expect(screen.getByTestId('buffering-spinner')).toBeInTheDocument();
      expect(screen.getByTestId('buffering-status')).toHaveTextContent('Buffering...');
    });

    it('should not display spinner when not buffering', () => {
      render(
        <BufferingIndicator
          bufferedPercentage={75}
          isBuffering={false}
          isError={false}
        />
      );

      expect(screen.queryByTestId('buffering-spinner')).not.toBeInTheDocument();
      // buffering-status is only shown when buffering or error is true
      expect(screen.queryByTestId('buffering-status')).not.toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('should display error message', () => {
      render(
        <BufferingIndicator
          bufferedPercentage={25}
          isError={true}
          errorMessage="Connection lost"
        />
      );

      expect(screen.getByTestId('buffering-status')).toHaveTextContent('Connection lost');
      expect(screen.queryByTestId('buffering-spinner')).not.toBeInTheDocument();
    });

    it('should display default error when no message provided', () => {
      render(
        <BufferingIndicator
          bufferedPercentage={25}
          isError={true}
        />
      );

      expect(screen.getByTestId('buffering-status')).toHaveTextContent('Playback error');
    });

    it('should prioritize error over buffering', () => {
      render(
        <BufferingIndicator
          bufferedPercentage={50}
          isBuffering={true}
          isError={true}
          errorMessage="Error"
        />
      );

      expect(screen.getByTestId('buffering-status')).toHaveTextContent('Error');
      expect(screen.queryByTestId('buffering-spinner')).not.toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('keeps the live region on the transitions only, not on the whole indicator (#6071)', () => {
      render(<BufferingIndicator bufferedPercentage={50} isBuffering={false} />);

      const indicator = screen.getByTestId('buffering-indicator');
      expect(indicator).not.toHaveAttribute('role');
      expect(indicator).not.toHaveAttribute('aria-live');
      const region = screen.getByTestId('buffering-live-region');
      expect(region).toHaveAttribute('role', 'status');
      expect(region).toHaveAttribute('aria-live', 'polite');
      expect(region).not.toHaveTextContent('%'); // idle: nothing to announce
    });

    it('a new percentage changes the progressbar value, never the live text (#6071)', () => {
      const { rerender } = render(<BufferingIndicator bufferedPercentage={25} isBuffering={true} />);
      const textBefore = screen.getByTestId('buffering-live-region').textContent;

      rerender(<BufferingIndicator bufferedPercentage={80} isBuffering={true} />);

      expect(screen.getByTestId('buffering-live-region').textContent).toBe(textBefore);
      const bar = screen.getByRole('progressbar');
      expect(bar).toHaveAttribute('aria-valuenow', '80');
      expect(bar).toHaveAttribute('aria-valuetext', '80%');
      expect(bar).toHaveAttribute('aria-label', 'Buffered content');
    });

    it('hides the visual percentage from assistive tech', () => {
      render(<BufferingIndicator bufferedPercentage={75} isBuffering={false} />);
      expect(screen.getByTestId('buffered-percentage')).toHaveAttribute('aria-hidden', 'true');
    });

    it('announces buffering and error through the live region', () => {
      const { rerender } = render(<BufferingIndicator bufferedPercentage={25} isBuffering={true} />);
      expect(screen.getByTestId('buffering-live-region')).toHaveTextContent('Buffering');

      rerender(
        <BufferingIndicator bufferedPercentage={25} isBuffering={false} isError={true} errorMessage="Stream failed" />
      );
      expect(screen.getByTestId('buffering-live-region')).toHaveTextContent('Stream failed');
    });

    it('should support custom aria-label on the progressbar', () => {
      render(<BufferingIndicator bufferedPercentage={50} isBuffering={false} ariaLabel="Custom label" />);
      expect(screen.getByRole('progressbar')).toHaveAttribute('aria-label', 'Custom label');
    });
  });

  describe('CSS & Styling', () => {
    it('should accept custom className', () => {
      const { container } = render(
        <BufferingIndicator
          bufferedPercentage={50}
          isBuffering={false}
          className="custom-class"
        />
      );

      expect(container.querySelector('.custom-class')).toBeInTheDocument();
    });

    it('should have proper test IDs', () => {
      render(
        <BufferingIndicator
          bufferedPercentage={50}
          isBuffering={true}
        />
      );

      expect(screen.getByTestId('buffering-indicator')).toBeInTheDocument();
      expect(screen.getByTestId('buffered-bar')).toBeInTheDocument();
      expect(screen.getByTestId('buffered-percentage')).toBeInTheDocument();
      expect(screen.getByTestId('buffering-status')).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should clamp negative percentage to 0', () => {
      render(
        <BufferingIndicator
          bufferedPercentage={-10}
          isBuffering={false}
        />
      );

      expect(screen.getByTestId('buffered-percentage')).toHaveTextContent('0%');
      expect(screen.getByTestId('buffered-bar')).toHaveStyle('width: 0%');
    });

    it('should clamp over-100 percentage to 100', () => {
      render(
        <BufferingIndicator
          bufferedPercentage={150}
          isBuffering={false}
        />
      );

      expect(screen.getByTestId('buffered-percentage')).toHaveTextContent('100%');
      expect(screen.getByTestId('buffered-bar')).toHaveStyle('width: 100%');
    });

    it('should handle NaN as 0%', () => {
      render(
        <BufferingIndicator
          bufferedPercentage={NaN}
          isBuffering={false}
        />
      );

      expect(screen.getByTestId('buffered-percentage')).toHaveTextContent('0%');
    });

    it('should handle Infinity as 100%', () => {
      render(
        <BufferingIndicator
          bufferedPercentage={Infinity}
          isBuffering={false}
        />
      );

      expect(screen.getByTestId('buffered-percentage')).toHaveTextContent('100%');
    });

    it('should handle empty error message', () => {
      render(
        <BufferingIndicator
          bufferedPercentage={50}
          isError={true}
          errorMessage=""
        />
      );

      expect(screen.getByTestId('buffering-status')).toHaveTextContent('Playback error');
    });
  });
});
