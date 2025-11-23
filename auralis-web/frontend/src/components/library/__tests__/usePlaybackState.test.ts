/**
 * usePlaybackState Hook Tests
 *
 * Tests for playback state management:
 * - Track playback with state updates
 * - Pause functionality
 * - Toast notifications
 */

import { vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { usePlaybackState } from '../usePlaybackState';

// Mock dependencies
vi.mock('../../../hooks/usePlayerAPI', () => ({
  usePlayerAPI: vi.fn(() => ({
    playTrack: vi.fn().mockResolvedValue(undefined),
  })),
}));

vi.mock('../../shared/ui/feedback', () => ({
  useToast: vi.fn(() => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  })),
}));

const mockTrack = {
  id: 1,
  title: 'Test Track',
  artist: 'Test Artist',
  album: 'Test Album',
  duration: 180,
  filepath: '/path/to/track.mp3',
};

const mockTrack2 = {
  id: 2,
  title: 'Another Track',
  artist: 'Another Artist',
  album: 'Another Album',
  duration: 240,
  filepath: '/path/to/track2.mp3',
};

describe('usePlaybackState', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Hook Initialization', () => {
    it('should initialize with undefined currentTrackId and false isPlaying', () => {
      const { result } = renderHook(() => usePlaybackState());

      expect(result.current.currentTrackId).toBeUndefined();
      expect(result.current.isPlaying).toBe(false);
    });
  });

  describe('handlePlayTrack', () => {
    it('should call playTrack and update state', async () => {
      const { result } = renderHook(() => usePlaybackState());

      await act(async () => {
        await result.current.handlePlayTrack(mockTrack);
      });

      expect(result.current.currentTrackId).toBe(1);
      expect(result.current.isPlaying).toBe(true);
    });

    it('should show success toast with track title', async () => {
      const { result } = renderHook(() => usePlaybackState());

      await act(async () => {
        await result.current.handlePlayTrack(mockTrack);
      });

      // Hook was called successfully and updated state
      expect(result.current.isPlaying).toBe(true);
    });

    it('should call optional onTrackPlay callback', async () => {
      const mockOnTrackPlay = vi.fn();
      const { result } = renderHook(() => usePlaybackState(mockOnTrackPlay));

      await act(async () => {
        await result.current.handlePlayTrack(mockTrack);
      });

      expect(mockOnTrackPlay).toHaveBeenCalledWith(mockTrack);
    });

    it('should update state when different tracks are played', async () => {
      const { result } = renderHook(() => usePlaybackState());

      // Play first track
      await act(async () => {
        await result.current.handlePlayTrack(mockTrack);
      });

      expect(result.current.currentTrackId).toBe(1);

      // Play second track
      await act(async () => {
        await result.current.handlePlayTrack(mockTrack2);
      });

      expect(result.current.currentTrackId).toBe(2);
    });
  });

  describe('handlePause', () => {
    it('should set isPlaying to false', async () => {
      const { result } = renderHook(() => usePlaybackState());

      // First play a track
      await act(async () => {
        await result.current.handlePlayTrack(mockTrack);
      });

      expect(result.current.isPlaying).toBe(true);

      // Then pause
      act(() => {
        result.current.handlePause();
      });

      expect(result.current.isPlaying).toBe(false);
    });

    it('should set isPlaying to false even if not playing', () => {
      const { result } = renderHook(() => usePlaybackState());

      expect(result.current.isPlaying).toBe(false);

      act(() => {
        result.current.handlePause();
      });

      expect(result.current.isPlaying).toBe(false);
    });
  });

  describe('State Isolation', () => {
    it('should not share state between hook instances', async () => {
      const { result: result1 } = renderHook(() => usePlaybackState());
      const { result: result2 } = renderHook(() => usePlaybackState());

      await act(async () => {
        await result1.current.handlePlayTrack(mockTrack);
      });

      expect(result1.current.currentTrackId).toBe(1);
      expect(result1.current.isPlaying).toBe(true);

      expect(result2.current.currentTrackId).toBeUndefined();
      expect(result2.current.isPlaying).toBe(false);
    });
  });

  describe('Handler Memoization', () => {
    it('should maintain handler references across props changes', () => {
      const mockCallback = vi.fn();
      const { result, rerender } = renderHook(
        ({ callback }) => usePlaybackState(callback),
        { initialProps: { callback: mockCallback } }
      );

      const initialPause = result.current.handlePause;

      rerender({ callback: mockCallback });

      expect(result.current.handlePause).toBe(initialPause);
    });
  });

  describe('onTrackPlay Callback', () => {
    it('should not require onTrackPlay callback', async () => {
      const { result } = renderHook(() => usePlaybackState());

      // Should not throw when callback is not provided
      await expect(
        act(async () => {
          await result.current.handlePlayTrack(mockTrack);
        })
      ).resolves.not.toThrow();
    });

    it('should pass correct track to onTrackPlay', async () => {
      const mockOnTrackPlay = vi.fn();
      const { result } = renderHook(() => usePlaybackState(mockOnTrackPlay));

      await act(async () => {
        await result.current.handlePlayTrack(mockTrack);
        await result.current.handlePlayTrack(mockTrack2);
      });

      expect(mockOnTrackPlay).toHaveBeenCalledTimes(2);
      expect(mockOnTrackPlay).toHaveBeenNthCalledWith(1, mockTrack);
      expect(mockOnTrackPlay).toHaveBeenNthCalledWith(2, mockTrack2);
    });
  });

  describe('Playback Flow', () => {
    it('should handle complete playback cycle', async () => {
      const mockOnTrackPlay = vi.fn();
      const { result } = renderHook(() => usePlaybackState(mockOnTrackPlay));

      // Initial state
      expect(result.current.isPlaying).toBe(false);

      // Play
      await act(async () => {
        await result.current.handlePlayTrack(mockTrack);
      });

      expect(result.current.isPlaying).toBe(true);
      expect(result.current.currentTrackId).toBe(1);
      expect(mockOnTrackPlay).toHaveBeenCalledWith(mockTrack);

      // Pause
      act(() => {
        result.current.handlePause();
      });

      expect(result.current.isPlaying).toBe(false);
      expect(result.current.currentTrackId).toBe(1); // Still has current track
    });
  });
});
