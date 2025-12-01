/**
 * PlaybackControls Component Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Comprehensive test suite for the PlaybackControls component.
 * Tests user interactions, loading states, and error handling.
 *
 * @module components/player/__tests__/PlaybackControls.test
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import PlaybackControls from '@/components/player/PlaybackControls';
import { usePlaybackState } from '@/hooks/player/usePlaybackState';
import { usePlaybackControl } from '@/hooks/player/usePlaybackControl';

// Mock the hooks
vi.mock('@/hooks/player/usePlaybackState');
vi.mock('@/hooks/player/usePlaybackControl');

describe('PlaybackControls', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('should render play button when not playing', () => {
      vi.mocked(usePlaybackState).mockReturnValue({
        currentTrack: null,
        isPlaying: false,
        volume: 0.5,
        position: 0,
        duration: 0,
        queue: [],
        queueIndex: -1,
        gapless_enabled: false,
        crossfade_enabled: false,
        crossfade_duration: 0,
        isLoading: false,
        error: null,
      });

      vi.mocked(usePlaybackControl).mockReturnValue({
        play: vi.fn(),
        pause: vi.fn(),
        stop: vi.fn(),
        seek: vi.fn(),
        next: vi.fn(),
        previous: vi.fn(),
        setVolume: vi.fn(),
        isLoading: false,
        error: null,
        clearError: vi.fn(),
      });

      render(<PlaybackControls />);

      expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
    });

    it('should render pause button when playing', () => {
      vi.mocked(usePlaybackState).mockReturnValue({
        currentTrack: null,
        isPlaying: true,
        volume: 0.5,
        position: 0,
        duration: 0,
        queue: [],
        queueIndex: -1,
        gapless_enabled: false,
        crossfade_enabled: false,
        crossfade_duration: 0,
        isLoading: false,
        error: null,
      });

      vi.mocked(usePlaybackControl).mockReturnValue({
        play: vi.fn(),
        pause: vi.fn(),
        stop: vi.fn(),
        seek: vi.fn(),
        next: vi.fn(),
        previous: vi.fn(),
        setVolume: vi.fn(),
        isLoading: false,
        error: null,
        clearError: vi.fn(),
      });

      render(<PlaybackControls />);

      expect(screen.getByRole('button', { name: /pause/i })).toBeInTheDocument();
    });

    it('should render next and previous buttons', () => {
      vi.mocked(usePlaybackState).mockReturnValue({
        currentTrack: null,
        isPlaying: false,
        volume: 0.5,
        position: 0,
        duration: 0,
        queue: [],
        queueIndex: -1,
        gapless_enabled: false,
        crossfade_enabled: false,
        crossfade_duration: 0,
        isLoading: false,
        error: null,
      });

      vi.mocked(usePlaybackControl).mockReturnValue({
        play: vi.fn(),
        pause: vi.fn(),
        stop: vi.fn(),
        seek: vi.fn(),
        next: vi.fn(),
        previous: vi.fn(),
        setVolume: vi.fn(),
        isLoading: false,
        error: null,
        clearError: vi.fn(),
      });

      render(<PlaybackControls />);

      expect(screen.getByRole('button', { name: /previous/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument();
    });
  });

  describe('user interactions', () => {
    it('should call play when play button is clicked', async () => {
      const mockPlay = vi.fn().mockResolvedValue(undefined);

      vi.mocked(usePlaybackState).mockReturnValue({
        currentTrack: null,
        isPlaying: false,
        volume: 0.5,
        position: 0,
        duration: 0,
        queue: [],
        queueIndex: -1,
        gapless_enabled: false,
        crossfade_enabled: false,
        crossfade_duration: 0,
        isLoading: false,
        error: null,
      });

      vi.mocked(usePlaybackControl).mockReturnValue({
        play: mockPlay,
        pause: vi.fn(),
        stop: vi.fn(),
        seek: vi.fn(),
        next: vi.fn(),
        previous: vi.fn(),
        setVolume: vi.fn(),
        isLoading: false,
        error: null,
        clearError: vi.fn(),
      });

      render(<PlaybackControls />);

      const playButton = screen.getByRole('button', { name: /play/i });
      fireEvent.click(playButton);

      await waitFor(() => {
        expect(mockPlay).toHaveBeenCalled();
      });
    });

    it('should call pause when pause button is clicked', async () => {
      const mockPause = vi.fn().mockResolvedValue(undefined);

      vi.mocked(usePlaybackState).mockReturnValue({
        currentTrack: null,
        isPlaying: true,
        volume: 0.5,
        position: 0,
        duration: 0,
        queue: [],
        queueIndex: -1,
        gapless_enabled: false,
        crossfade_enabled: false,
        crossfade_duration: 0,
        isLoading: false,
        error: null,
      });

      vi.mocked(usePlaybackControl).mockReturnValue({
        play: vi.fn(),
        pause: mockPause,
        stop: vi.fn(),
        seek: vi.fn(),
        next: vi.fn(),
        previous: vi.fn(),
        setVolume: vi.fn(),
        isLoading: false,
        error: null,
        clearError: vi.fn(),
      });

      render(<PlaybackControls />);

      const pauseButton = screen.getByRole('button', { name: /pause/i });
      fireEvent.click(pauseButton);

      await waitFor(() => {
        expect(mockPause).toHaveBeenCalled();
      });
    });

    it('should call next when next button is clicked', async () => {
      const mockNext = vi.fn().mockResolvedValue(undefined);

      vi.mocked(usePlaybackState).mockReturnValue({
        currentTrack: null,
        isPlaying: false,
        volume: 0.5,
        position: 0,
        duration: 0,
        queue: [],
        queueIndex: -1,
        gapless_enabled: false,
        crossfade_enabled: false,
        crossfade_duration: 0,
        isLoading: false,
        error: null,
      });

      vi.mocked(usePlaybackControl).mockReturnValue({
        play: vi.fn(),
        pause: vi.fn(),
        stop: vi.fn(),
        seek: vi.fn(),
        next: mockNext,
        previous: vi.fn(),
        setVolume: vi.fn(),
        isLoading: false,
        error: null,
        clearError: vi.fn(),
      });

      render(<PlaybackControls />);

      const nextButton = screen.getByRole('button', { name: /next/i });
      fireEvent.click(nextButton);

      await waitFor(() => {
        expect(mockNext).toHaveBeenCalled();
      });
    });

    it('should call previous when previous button is clicked', async () => {
      const mockPrevious = vi.fn().mockResolvedValue(undefined);

      vi.mocked(usePlaybackState).mockReturnValue({
        currentTrack: null,
        isPlaying: false,
        volume: 0.5,
        position: 0,
        duration: 0,
        queue: [],
        queueIndex: -1,
        gapless_enabled: false,
        crossfade_enabled: false,
        crossfade_duration: 0,
        isLoading: false,
        error: null,
      });

      vi.mocked(usePlaybackControl).mockReturnValue({
        play: vi.fn(),
        pause: vi.fn(),
        stop: vi.fn(),
        seek: vi.fn(),
        next: vi.fn(),
        previous: mockPrevious,
        setVolume: vi.fn(),
        isLoading: false,
        error: null,
        clearError: vi.fn(),
      });

      render(<PlaybackControls />);

      const previousButton = screen.getByRole('button', { name: /previous/i });
      fireEvent.click(previousButton);

      await waitFor(() => {
        expect(mockPrevious).toHaveBeenCalled();
      });
    });
  });

  describe('loading state', () => {
    it('should disable buttons when isLoading is true', () => {
      vi.mocked(usePlaybackState).mockReturnValue({
        currentTrack: null,
        isPlaying: false,
        volume: 0.5,
        position: 0,
        duration: 0,
        queue: [],
        queueIndex: -1,
        gapless_enabled: false,
        crossfade_enabled: false,
        crossfade_duration: 0,
        isLoading: false,
        error: null,
      });

      vi.mocked(usePlaybackControl).mockReturnValue({
        play: vi.fn(),
        pause: vi.fn(),
        stop: vi.fn(),
        seek: vi.fn(),
        next: vi.fn(),
        previous: vi.fn(),
        setVolume: vi.fn(),
        isLoading: true,
        error: null,
        clearError: vi.fn(),
      });

      render(<PlaybackControls />);

      const buttons = screen.getAllByRole('button');
      buttons.forEach((button) => {
        expect(button).toBeDisabled();
      });
    });

    it('should show loading indicator when isLoading is true', () => {
      vi.mocked(usePlaybackState).mockReturnValue({
        currentTrack: null,
        isPlaying: false,
        volume: 0.5,
        position: 0,
        duration: 0,
        queue: [],
        queueIndex: -1,
        gapless_enabled: false,
        crossfade_enabled: false,
        crossfade_duration: 0,
        isLoading: false,
        error: null,
      });

      vi.mocked(usePlaybackControl).mockReturnValue({
        play: vi.fn(),
        pause: vi.fn(),
        stop: vi.fn(),
        seek: vi.fn(),
        next: vi.fn(),
        previous: vi.fn(),
        setVolume: vi.fn(),
        isLoading: true,
        error: null,
        clearError: vi.fn(),
      });

      render(<PlaybackControls />);

      expect(screen.getByText(/loading/i)).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('should display error message when error exists', () => {
      const errorMessage = 'Failed to play';

      vi.mocked(usePlaybackState).mockReturnValue({
        currentTrack: null,
        isPlaying: false,
        volume: 0.5,
        position: 0,
        duration: 0,
        queue: [],
        queueIndex: -1,
        gapless_enabled: false,
        crossfade_enabled: false,
        crossfade_duration: 0,
        isLoading: false,
        error: null,
      });

      vi.mocked(usePlaybackControl).mockReturnValue({
        play: vi.fn(),
        pause: vi.fn(),
        stop: vi.fn(),
        seek: vi.fn(),
        next: vi.fn(),
        previous: vi.fn(),
        setVolume: vi.fn(),
        isLoading: false,
        error: { message: errorMessage, code: 'PLAY_ERROR', status: 500 },
        clearError: vi.fn(),
      });

      render(<PlaybackControls />);

      expect(screen.getByText(errorMessage)).toBeInTheDocument();
    });

    it('should not display error when error is null', () => {
      vi.mocked(usePlaybackState).mockReturnValue({
        currentTrack: null,
        isPlaying: false,
        volume: 0.5,
        position: 0,
        duration: 0,
        queue: [],
        queueIndex: -1,
        gapless_enabled: false,
        crossfade_enabled: false,
        crossfade_duration: 0,
        isLoading: false,
        error: null,
      });

      vi.mocked(usePlaybackControl).mockReturnValue({
        play: vi.fn(),
        pause: vi.fn(),
        stop: vi.fn(),
        seek: vi.fn(),
        next: vi.fn(),
        previous: vi.fn(),
        setVolume: vi.fn(),
        isLoading: false,
        error: null,
        clearError: vi.fn(),
      });

      const { container } = render(<PlaybackControls />);

      const errorElements = container.querySelectorAll('[style*="error"]');
      expect(errorElements.length).toBe(0);
    });
  });

  describe('accessibility', () => {
    it('should have proper aria-labels on buttons', () => {
      vi.mocked(usePlaybackState).mockReturnValue({
        currentTrack: null,
        isPlaying: false,
        volume: 0.5,
        position: 0,
        duration: 0,
        queue: [],
        queueIndex: -1,
        gapless_enabled: false,
        crossfade_enabled: false,
        crossfade_duration: 0,
        isLoading: false,
        error: null,
      });

      vi.mocked(usePlaybackControl).mockReturnValue({
        play: vi.fn(),
        pause: vi.fn(),
        stop: vi.fn(),
        seek: vi.fn(),
        next: vi.fn(),
        previous: vi.fn(),
        setVolume: vi.fn(),
        isLoading: false,
        error: null,
        clearError: vi.fn(),
      });

      render(<PlaybackControls />);

      expect(screen.getByRole('button', { name: /play/i })).toHaveAttribute(
        'aria-label',
        'Play'
      );
      expect(screen.getByRole('button', { name: /next/i })).toHaveAttribute(
        'aria-label',
        'Next track'
      );
    });

    it('should have keyboard navigation support', () => {
      vi.mocked(usePlaybackState).mockReturnValue({
        currentTrack: null,
        isPlaying: false,
        volume: 0.5,
        position: 0,
        duration: 0,
        queue: [],
        queueIndex: -1,
        gapless_enabled: false,
        crossfade_enabled: false,
        crossfade_duration: 0,
        isLoading: false,
        error: null,
      });

      vi.mocked(usePlaybackControl).mockReturnValue({
        play: vi.fn(),
        pause: vi.fn(),
        stop: vi.fn(),
        seek: vi.fn(),
        next: vi.fn(),
        previous: vi.fn(),
        setVolume: vi.fn(),
        isLoading: false,
        error: null,
        clearError: vi.fn(),
      });

      render(<PlaybackControls />);

      const playButton = screen.getByRole('button', { name: /play/i });
      expect(playButton.tagName).toBe('BUTTON');
    });
  });
});
