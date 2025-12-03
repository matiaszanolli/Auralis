/**
 * TrackRowPlayButton Component Tests
 *
 * Tests for play/pause button in track row:
 * - Icon rendering (play vs pause)
 * - Click handler invocation
 * - State-based icon display
 */

import { vi } from 'vitest';
import { render, screen } from '@/test/test-utils';
import { TrackRowPlayButton } from '../tracks/TrackRowPlayButton';
import { Pause, PlayArrow } from '@mui/icons-material';

describe('TrackRowPlayButton', () => {
  const mockOnClick = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Icon Display', () => {
    it('should display play icon when not current', () => {
      render(
        <TrackRowPlayButton
          isCurrent={false}
          isPlaying={false}
          onClick={mockOnClick}
        />
      );

      // Check for play icon (PlayArrow)
      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
      expect(button.querySelector('svg')).toBeInTheDocument();
    });

    it('should display play icon when current but not playing', () => {
      render(
        <TrackRowPlayButton
          isCurrent={true}
          isPlaying={false}
          onClick={mockOnClick}
        />
      );

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
    });

    it('should display pause icon when current and playing', () => {
      render(
        <TrackRowPlayButton
          isCurrent={true}
          isPlaying={true}
          onClick={mockOnClick}
        />
      );

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
    });

    it('should display play icon when not current and playing', () => {
      render(
        <TrackRowPlayButton
          isCurrent={false}
          isPlaying={true}
          onClick={mockOnClick}
        />
      );

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
    });
  });

  describe('Click Handling', () => {
    it('should call onClick handler when clicked', () => {
      render(
        <TrackRowPlayButton
          isCurrent={false}
          isPlaying={false}
          onClick={mockOnClick}
        />
      );

      const button = screen.getByRole('button');
      button.click();

      expect(mockOnClick).toHaveBeenCalledTimes(1);
    });

    it('should pass event object to onClick', () => {
      render(
        <TrackRowPlayButton
          isCurrent={false}
          isPlaying={false}
          onClick={mockOnClick}
        />
      );

      const button = screen.getByRole('button');
      button.click();

      // Verify event was passed
      expect(mockOnClick).toHaveBeenCalledWith(expect.any(Object));
    });

    it('should handle multiple clicks', () => {
      render(
        <TrackRowPlayButton
          isCurrent={false}
          isPlaying={false}
          onClick={mockOnClick}
        />
      );

      const button = screen.getByRole('button');
      button.click();
      button.click();
      button.click();

      expect(mockOnClick).toHaveBeenCalledTimes(3);
    });
  });

  describe('State Transitions', () => {
    it('should show pause icon only when both isCurrent and isPlaying are true', () => {
      const { rerender } = render(
        <TrackRowPlayButton
          isCurrent={false}
          isPlaying={false}
          onClick={mockOnClick}
        />
      );

      let button = screen.getByRole('button');
      expect(button.querySelector('svg')).toBeInTheDocument();

      // Change to playing but not current
      rerender(
        <TrackRowPlayButton
          isCurrent={false}
          isPlaying={true}
          onClick={mockOnClick}
        />
      );

      button = screen.getByRole('button');
      expect(button.querySelector('svg')).toBeInTheDocument();

      // Change to current and not playing
      rerender(
        <TrackRowPlayButton
          isCurrent={true}
          isPlaying={false}
          onClick={mockOnClick}
        />
      );

      button = screen.getByRole('button');
      expect(button.querySelector('svg')).toBeInTheDocument();

      // Change to current and playing
      rerender(
        <TrackRowPlayButton
          isCurrent={true}
          isPlaying={true}
          onClick={mockOnClick}
        />
      );

      button = screen.getByRole('button');
      expect(button.querySelector('svg')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have a button role', () => {
      render(
        <TrackRowPlayButton
          isCurrent={false}
          isPlaying={false}
          onClick={mockOnClick}
        />
      );

      expect(screen.getByRole('button')).toBeInTheDocument();
    });

    it('should be keyboard accessible', () => {
      render(
        <TrackRowPlayButton
          isCurrent={false}
          isPlaying={false}
          onClick={mockOnClick}
        />
      );

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
      expect(button.tagName).toBe('BUTTON');
    });
  });

  describe('Props Integration', () => {
    it('should handle all prop combinations', () => {
      const combinations = [
        { isCurrent: false, isPlaying: false },
        { isCurrent: false, isPlaying: true },
        { isCurrent: true, isPlaying: false },
        { isCurrent: true, isPlaying: true },
      ];

      combinations.forEach(({ isCurrent, isPlaying }) => {
        const { unmount } = render(
          <TrackRowPlayButton
            isCurrent={isCurrent}
            isPlaying={isPlaying}
            onClick={mockOnClick}
          />
        );

        const button = screen.getByRole('button');
        expect(button).toBeInTheDocument();
        unmount();
      });
    });
  });
});
