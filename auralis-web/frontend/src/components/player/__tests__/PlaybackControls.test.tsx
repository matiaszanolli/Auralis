/**
 * PlaybackControls Component Tests
 *
 * Tests for playback control buttons (play, pause, next, previous),
 * button states, loading indicators, and accessibility features.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@/test/test-utils';
import PlaybackControls from '../PlaybackControls';

describe('PlaybackControls', () => {
  describe('Basic Rendering', () => {
    it('should render all control buttons', () => {
      render(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
        />
      );

      expect(screen.getByTestId('playback-controls')).toBeInTheDocument();
      expect(screen.getByTestId('playback-controls-previous')).toBeInTheDocument();
      expect(screen.getByTestId('playback-controls-play')).toBeInTheDocument();
      expect(screen.getByTestId('playback-controls-next')).toBeInTheDocument();
    });

    it('should render with correct structure', () => {
      render(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
        />
      );

      const controls = screen.getByTestId('playback-controls');
      expect(controls).toHaveStyle('display: flex');
    });
  });

  describe('Play/Pause State', () => {
    it('should show play button when not playing', () => {
      render(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
        />
      );

      expect(screen.getByTestId('playback-controls-play')).toBeInTheDocument();
      expect(screen.queryByTestId('playback-controls-pause')).not.toBeInTheDocument();
    });

    it('should show pause button when playing', () => {
      render(
        <PlaybackControls
          isPlaying={true}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
        />
      );

      expect(screen.getByTestId('playback-controls-pause')).toBeInTheDocument();
      expect(screen.queryByTestId('playback-controls-play')).not.toBeInTheDocument();
    });

    it('should toggle between play and pause icons', () => {
      const { rerender } = render(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
        />
      );

      expect(screen.getByTestId('playback-controls-play')).toBeInTheDocument();

      rerender(
        <PlaybackControls
          isPlaying={true}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
        />
      );

      expect(screen.getByTestId('playback-controls-pause')).toBeInTheDocument();
    });
  });

  describe('Button Clicks', () => {
    it('should call onPlay when play button clicked', () => {
      const mockPlay = vi.fn();
      render(
        <PlaybackControls
          isPlaying={false}
          onPlay={mockPlay}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
        />
      );

      fireEvent.click(screen.getByTestId('playback-controls-play'));

      expect(mockPlay).toHaveBeenCalledTimes(1);
    });

    it('should call onPause when pause button clicked', () => {
      const mockPause = vi.fn();
      render(
        <PlaybackControls
          isPlaying={true}
          onPlay={vi.fn()}
          onPause={mockPause}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
        />
      );

      fireEvent.click(screen.getByTestId('playback-controls-pause'));

      expect(mockPause).toHaveBeenCalledTimes(1);
    });

    it('should call onNext when next button clicked', () => {
      const mockNext = vi.fn();
      render(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={mockNext}
          onPrevious={vi.fn()}
        />
      );

      fireEvent.click(screen.getByTestId('playback-controls-next'));

      expect(mockNext).toHaveBeenCalledTimes(1);
    });

    it('should call onPrevious when previous button clicked', () => {
      const mockPrevious = vi.fn();
      render(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={mockPrevious}
        />
      );

      fireEvent.click(screen.getByTestId('playback-controls-previous'));

      expect(mockPrevious).toHaveBeenCalledTimes(1);
    });

    it('should not call callbacks when disabled', () => {
      const mockPlay = vi.fn();
      const mockNext = vi.fn();
      render(
        <PlaybackControls
          isPlaying={false}
          onPlay={mockPlay}
          onPause={vi.fn()}
          onNext={mockNext}
          onPrevious={vi.fn()}
          disabled={true}
        />
      );

      fireEvent.click(screen.getByTestId('playback-controls-play'));
      fireEvent.click(screen.getByTestId('playback-controls-next'));

      expect(mockPlay).not.toHaveBeenCalled();
      expect(mockNext).not.toHaveBeenCalled();
    });

    it('should not call callbacks when loading', () => {
      const mockPlay = vi.fn();
      const mockPrevious = vi.fn();
      render(
        <PlaybackControls
          isPlaying={false}
          onPlay={mockPlay}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={mockPrevious}
          isLoading={true}
        />
      );

      fireEvent.click(screen.getByTestId('playback-controls-play'));
      fireEvent.click(screen.getByTestId('playback-controls-previous'));

      expect(mockPlay).not.toHaveBeenCalled();
      expect(mockPrevious).not.toHaveBeenCalled();
    });
  });

  describe('Loading State', () => {
    it('should show loading indicator when isLoading is true', () => {
      render(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
          isLoading={true}
        />
      );

      expect(screen.getByTestId('playback-controls-loading')).toBeInTheDocument();
      expect(screen.getByTestId('playback-controls-loading')).toHaveTextContent('Loading...');
    });

    it('should not show loading indicator when isLoading is false', () => {
      render(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
          isLoading={false}
        />
      );

      expect(screen.queryByTestId('playback-controls-loading')).not.toBeInTheDocument();
    });

    it('should disable all buttons when loading', () => {
      render(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
          isLoading={true}
        />
      );

      expect(screen.getByTestId('playback-controls-play')).toBeDisabled();
      expect(screen.getByTestId('playback-controls-previous')).toBeDisabled();
      expect(screen.getByTestId('playback-controls-next')).toBeDisabled();
    });
  });

  describe('Disabled State', () => {
    it('should disable all buttons when disabled is true', () => {
      render(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
          disabled={true}
        />
      );

      expect(screen.getByTestId('playback-controls-play')).toBeDisabled();
      expect(screen.getByTestId('playback-controls-previous')).toBeDisabled();
      expect(screen.getByTestId('playback-controls-next')).toBeDisabled();
    });

    it('should enable all buttons when disabled is false', () => {
      render(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
          disabled={false}
        />
      );

      expect(screen.getByTestId('playback-controls-play')).not.toBeDisabled();
      expect(screen.getByTestId('playback-controls-previous')).not.toBeDisabled();
      expect(screen.getByTestId('playback-controls-next')).not.toBeDisabled();
    });

    it('should show disabled cursor when disabled', () => {
      render(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
          disabled={true}
        />
      );

      const playButton = screen.getByTestId('playback-controls-play');
      expect(playButton).toHaveStyle('cursor: not-allowed');
    });
  });

  describe('Accessibility', () => {
    it('should have play aria-label', () => {
      render(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
        />
      );

      expect(screen.getByTestId('playback-controls-play')).toHaveAttribute('aria-label', 'Play');
    });

    it('should have pause aria-label', () => {
      render(
        <PlaybackControls
          isPlaying={true}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
        />
      );

      expect(screen.getByTestId('playback-controls-pause')).toHaveAttribute('aria-label', 'Pause');
    });

    it('should have next aria-label', () => {
      render(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
        />
      );

      expect(screen.getByTestId('playback-controls-next')).toHaveAttribute('aria-label', 'Next track');
    });

    it('should have previous aria-label', () => {
      render(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
        />
      );

      expect(screen.getByTestId('playback-controls-previous')).toHaveAttribute('aria-label', 'Previous track');
    });

    it('should have title tooltips on buttons', () => {
      render(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
        />
      );

      // Tooltips include keyboard shortcuts for better UX
      expect(screen.getByTestId('playback-controls-play')).toHaveAttribute('title', 'Play (⌨ Space )');
      expect(screen.getByTestId('playback-controls-previous')).toHaveAttribute('title', 'Previous track (⌨ ← )');
      expect(screen.getByTestId('playback-controls-next')).toHaveAttribute('title', 'Next track (⌨ → )');
    });
  });

  describe('CSS & Styling', () => {
    it('should accept custom className', () => {
      const { container } = render(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
          className="custom-controls"
        />
      );

      expect(container.querySelector('.custom-controls')).toBeInTheDocument();
    });

    it('should have proper test IDs for all buttons', () => {
      render(
        <PlaybackControls
          isPlaying={true}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
        />
      );

      expect(screen.getByTestId('playback-controls')).toBeInTheDocument();
      expect(screen.getByTestId('playback-controls-previous')).toBeInTheDocument();
      expect(screen.getByTestId('playback-controls-pause')).toBeInTheDocument();
      expect(screen.getByTestId('playback-controls-next')).toBeInTheDocument();
    });

    it('should have pointer cursor when enabled', () => {
      render(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
          disabled={false}
        />
      );

      const playButton = screen.getByTestId('playback-controls-play');
      expect(playButton).toHaveStyle('cursor: pointer');
    });

    it('should have reduced opacity when disabled', () => {
      render(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
          disabled={true}
        />
      );

      const playButton = screen.getByTestId('playback-controls-play');
      expect(playButton).toHaveStyle('opacity: 0.5');
    });

    it('should have full opacity when enabled', () => {
      render(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
          disabled={false}
        />
      );

      const playButton = screen.getByTestId('playback-controls-play');
      expect(playButton).toHaveStyle('opacity: 1');
    });
  });

  describe('Realistic Scenarios', () => {
    it('should handle play and pause sequence', () => {
      const { rerender } = render(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
        />
      );

      expect(screen.getByTestId('playback-controls-play')).toBeInTheDocument();

      rerender(
        <PlaybackControls
          isPlaying={true}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
        />
      );

      expect(screen.getByTestId('playback-controls-pause')).toBeInTheDocument();

      rerender(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
        />
      );

      expect(screen.getByTestId('playback-controls-play')).toBeInTheDocument();
    });

    it('should handle loading state transitions', () => {
      const { rerender } = render(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
          isLoading={false}
        />
      );

      expect(screen.queryByTestId('playback-controls-loading')).not.toBeInTheDocument();

      rerender(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
          isLoading={true}
        />
      );

      expect(screen.getByTestId('playback-controls-loading')).toBeInTheDocument();

      rerender(
        <PlaybackControls
          isPlaying={true}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
          isLoading={false}
        />
      );

      expect(screen.queryByTestId('playback-controls-loading')).not.toBeInTheDocument();
    });

    it('should handle disabled state changes', () => {
      const { rerender } = render(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
          disabled={false}
        />
      );

      expect(screen.getByTestId('playback-controls-play')).not.toBeDisabled();

      rerender(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
          disabled={true}
        />
      );

      expect(screen.getByTestId('playback-controls-play')).toBeDisabled();

      rerender(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
          disabled={false}
        />
      );

      expect(screen.getByTestId('playback-controls-play')).not.toBeDisabled();
    });
  });

  describe('Props Updates', () => {
    it('should update when isPlaying changes', () => {
      const { rerender } = render(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
        />
      );

      expect(screen.getByTestId('playback-controls-play')).toBeInTheDocument();

      rerender(
        <PlaybackControls
          isPlaying={true}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
        />
      );

      expect(screen.getByTestId('playback-controls-pause')).toBeInTheDocument();
    });

    it('should update when isLoading changes', () => {
      const { rerender } = render(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
          isLoading={false}
        />
      );

      expect(screen.queryByTestId('playback-controls-loading')).not.toBeInTheDocument();

      rerender(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
          isLoading={true}
        />
      );

      expect(screen.getByTestId('playback-controls-loading')).toBeInTheDocument();
    });

    it('should update when disabled changes', () => {
      const { rerender } = render(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
          disabled={false}
        />
      );

      expect(screen.getByTestId('playback-controls-play')).not.toBeDisabled();

      rerender(
        <PlaybackControls
          isPlaying={false}
          onPlay={vi.fn()}
          onPause={vi.fn()}
          onNext={vi.fn()}
          onPrevious={vi.fn()}
          disabled={true}
        />
      );

      expect(screen.getByTestId('playback-controls-play')).toBeDisabled();
    });
  });
});
