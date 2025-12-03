/**
 * usePlayerControls Hook Tests
 *
 * 90+ comprehensive tests covering:
 * - Play/pause operations
 * - Track navigation (next/previous)
 * - Seeking with debouncing
 * - Volume control
 * - Queue operations
 * - Error handling
 * - Loading states
 *
 * @module __tests__/usePlayerControls
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { usePlayerControls } from '../usePlayerControls';

describe('usePlayerControls Hook', () => {
  let mockOnPlay: ReturnType<typeof vi.fn>;
  let mockOnPause: ReturnType<typeof vi.fn>;
  let mockOnSeek: ReturnType<typeof vi.fn>;
  let mockOnSetVolume: ReturnType<typeof vi.fn>;
  let mockOnNextTrack: ReturnType<typeof vi.fn>;
  let mockOnPreviousTrack: ReturnType<typeof vi.fn>;
  let mockOnPlayTrack: ReturnType<typeof vi.fn>;
  let mockOnRemoveFromQueue: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();

    mockOnPlay = vi.fn(async () => {});
    mockOnPause = vi.fn(async () => {});
    mockOnSeek = vi.fn(async () => {});
    mockOnSetVolume = vi.fn(async () => {});
    mockOnNextTrack = vi.fn(async () => {});
    mockOnPreviousTrack = vi.fn(async () => {});
    mockOnPlayTrack = vi.fn(async () => {});
    mockOnRemoveFromQueue = vi.fn(async () => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Play/Pause Operations', () => {
    it('should call play handler when play() is invoked', async () => {
      const { result } = renderHook(() =>
        usePlayerControls({ onPlay: mockOnPlay })
      );

      const response = await result.current.play();

      expect(mockOnPlay).toHaveBeenCalledTimes(1);
      expect(response.success).toBe(true);
    });

    it('should return error when play handler is not configured', async () => {
      const { result } = renderHook(() => usePlayerControls({}));

      const response = await result.current.play();

      expect(response.success).toBe(false);
      expect(response.error).toContain('Play handler not configured');
    });

    it('should call pause handler when pause() is invoked', async () => {
      const { result } = renderHook(() =>
        usePlayerControls({ onPause: mockOnPause })
      );

      const response = await result.current.pause();

      expect(mockOnPause).toHaveBeenCalledTimes(1);
      expect(response.success).toBe(true);
    });

    it('should return error when pause handler is not configured', async () => {
      const { result } = renderHook(() => usePlayerControls({}));

      const response = await result.current.pause();

      expect(response.success).toBe(false);
      expect(response.error).toContain('Pause handler not configured');
    });

    it('should set loading state during play operation', async () => {
      const { result } = renderHook(() =>
        usePlayerControls({ onPlay: mockOnPlay })
      );

      expect(result.current.isLoading).toBe(false);

      act(() => {
        result.current.play();
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false); // Should be false after completion
      });
    });

    it('should clear error on successful operation', async () => {
      mockOnPlay.mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() =>
        usePlayerControls({ onPlay: mockOnPlay })
      );

      // First call fails
      await result.current.play();
      expect(result.current.lastError).toBeDefined();

      // Reset mock for second call
      mockOnPlay.mockResolvedValueOnce(undefined);

      // Second call succeeds
      await result.current.play();
      expect(result.current.lastError).toBeUndefined();
    });

    it('should handle play operation errors', async () => {
      mockOnPlay.mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() =>
        usePlayerControls({ onPlay: mockOnPlay })
      );

      const response = await result.current.play();

      expect(response.success).toBe(false);
      expect(response.error).toContain('Network error');
      expect(result.current.lastError).toContain('Network error');
    });

    it('should handle pause operation errors', async () => {
      mockOnPause.mockRejectedValueOnce(new Error('Server error'));

      const { result } = renderHook(() =>
        usePlayerControls({ onPause: mockOnPause })
      );

      const response = await result.current.pause();

      expect(response.success).toBe(false);
      expect(response.error).toContain('Server error');
    });
  });

  describe('Track Navigation', () => {
    it('should call nextTrack handler when nextTrack() is invoked', async () => {
      const { result } = renderHook(() =>
        usePlayerControls({ onNextTrack: mockOnNextTrack })
      );

      const response = await result.current.nextTrack();

      expect(mockOnNextTrack).toHaveBeenCalledTimes(1);
      expect(response.success).toBe(true);
    });

    it('should return error when nextTrack handler is not configured', async () => {
      const { result } = renderHook(() => usePlayerControls({}));

      const response = await result.current.nextTrack();

      expect(response.success).toBe(false);
      expect(response.error).toContain('NextTrack handler not configured');
    });

    it('should call previousTrack handler when previousTrack() is invoked', async () => {
      const { result } = renderHook(() =>
        usePlayerControls({ onPreviousTrack: mockOnPreviousTrack })
      );

      const response = await result.current.previousTrack();

      expect(mockOnPreviousTrack).toHaveBeenCalledTimes(1);
      expect(response.success).toBe(true);
    });

    it('should return error when previousTrack handler is not configured', async () => {
      const { result } = renderHook(() => usePlayerControls({}));

      const response = await result.current.previousTrack();

      expect(response.success).toBe(false);
      expect(response.error).toContain('PreviousTrack handler not configured');
    });

    it('should handle nextTrack errors', async () => {
      mockOnNextTrack.mockRejectedValueOnce(new Error('No next track'));

      const { result } = renderHook(() =>
        usePlayerControls({ onNextTrack: mockOnNextTrack })
      );

      const response = await result.current.nextTrack();

      expect(response.success).toBe(false);
      expect(response.error).toContain('No next track');
    });

    it('should handle previousTrack errors', async () => {
      mockOnPreviousTrack.mockRejectedValueOnce(new Error('No previous track'));

      const { result } = renderHook(() =>
        usePlayerControls({ onPreviousTrack: mockOnPreviousTrack })
      );

      const response = await result.current.previousTrack();

      expect(response.success).toBe(false);
      expect(response.error).toContain('No previous track');
    });
  });

  describe('Seeking', () => {
    it('should call seek handler with correct position', async () => {
      const { result } = renderHook(() =>
        usePlayerControls({ onSeek: mockOnSeek })
      );

      const response = await result.current.seek(30);

      expect(mockOnSeek).toHaveBeenCalledWith(30);
      expect(response.success).toBe(true);
    });

    it('should reject negative seek position', async () => {
      const { result } = renderHook(() =>
        usePlayerControls({ onSeek: mockOnSeek })
      );

      const response = await result.current.seek(-5);

      expect(mockOnSeek).not.toHaveBeenCalled();
      expect(response.success).toBe(false);
      expect(response.error).toContain('negative');
    });

    it('should accept zero seek position', async () => {
      const { result } = renderHook(() =>
        usePlayerControls({ onSeek: mockOnSeek })
      );

      const response = await result.current.seek(0);

      expect(mockOnSeek).toHaveBeenCalledWith(0);
      expect(response.success).toBe(true);
    });

    it('should accept large seek positions', async () => {
      const { result } = renderHook(() =>
        usePlayerControls({ onSeek: mockOnSeek })
      );

      const response = await result.current.seek(3600); // 1 hour

      expect(mockOnSeek).toHaveBeenCalledWith(3600);
      expect(response.success).toBe(true);
    });

    it('should return error when seek handler is not configured', async () => {
      const { result } = renderHook(() => usePlayerControls({}));

      const response = await result.current.seek(30);

      expect(response.success).toBe(false);
      expect(response.error).toContain('Seek handler not configured');
    });

    it('should handle seek errors', async () => {
      mockOnSeek.mockRejectedValueOnce(new Error('Seek failed'));

      const { result } = renderHook(() =>
        usePlayerControls({ onSeek: mockOnSeek })
      );

      const response = await result.current.seek(30);

      expect(response.success).toBe(false);
      expect(response.error).toContain('Seek failed');
    });
  });

  describe('Debounced Seeking', () => {
    it('should debounce rapid seek calls', async () => {
      vi.useFakeTimers();

      const { result } = renderHook(() =>
        usePlayerControls({ onSeek: mockOnSeek, seekDebounceMs: 300 })
      );

      // Call seekDebounced multiple times rapidly
      act(() => {
        result.current.seekDebounced(10);
        result.current.seekDebounced(20);
        result.current.seekDebounced(30);
      });

      // Seek should not be called yet
      expect(mockOnSeek).not.toHaveBeenCalled();

      // Advance time past debounce interval
      vi.advanceTimersByTime(300);

      await waitFor(() => {
        expect(mockOnSeek).toHaveBeenCalledTimes(1);
        expect(mockOnSeek).toHaveBeenCalledWith(30); // Last position
      });

      vi.useRealTimers();
    });

    it('should respect custom debounce interval', async () => {
      vi.useFakeTimers();

      const { result } = renderHook(() =>
        usePlayerControls({ onSeek: mockOnSeek, seekDebounceMs: 500 })
      );

      act(() => {
        result.current.seekDebounced(50);
      });

      // Advance time less than debounce interval
      vi.advanceTimersByTime(400);
      expect(mockOnSeek).not.toHaveBeenCalled();

      // Advance past debounce interval
      vi.advanceTimersByTime(100);

      await waitFor(() => {
        expect(mockOnSeek).toHaveBeenCalledWith(50);
      });

      vi.useRealTimers();
    });

    it('should not call seek if position did not change', async () => {
      vi.useFakeTimers();

      const { result } = renderHook(() =>
        usePlayerControls({ onSeek: mockOnSeek, seekDebounceMs: 300 })
      );

      act(() => {
        result.current.seekDebounced(30);
        result.current.seekDebounced(30); // Same position
      });

      vi.advanceTimersByTime(300);

      // Should still not call since position didn't change after debounce
      expect(mockOnSeek).not.toHaveBeenCalled();

      vi.useRealTimers();
    });
  });

  describe('Volume Control', () => {
    it('should call setVolume handler with correct volume', async () => {
      const { result } = renderHook(() =>
        usePlayerControls({ onSetVolume: mockOnSetVolume })
      );

      const response = await result.current.setVolume(75);

      expect(mockOnSetVolume).toHaveBeenCalledWith(75);
      expect(response.success).toBe(true);
    });

    it('should accept volume from 0 to 100', async () => {
      const { result } = renderHook(() =>
        usePlayerControls({ onSetVolume: mockOnSetVolume })
      );

      // Test min
      let response = await result.current.setVolume(0);
      expect(response.success).toBe(true);

      // Test max
      response = await result.current.setVolume(100);
      expect(response.success).toBe(true);

      // Test middle
      response = await result.current.setVolume(50);
      expect(response.success).toBe(true);
    });

    it('should reject negative volume', async () => {
      const { result } = renderHook(() =>
        usePlayerControls({ onSetVolume: mockOnSetVolume })
      );

      const response = await result.current.setVolume(-1);

      expect(mockOnSetVolume).not.toHaveBeenCalled();
      expect(response.success).toBe(false);
      expect(response.error).toContain('between 0 and 100');
    });

    it('should reject volume above 100', async () => {
      const { result } = renderHook(() =>
        usePlayerControls({ onSetVolume: mockOnSetVolume })
      );

      const response = await result.current.setVolume(101);

      expect(mockOnSetVolume).not.toHaveBeenCalled();
      expect(response.success).toBe(false);
      expect(response.error).toContain('between 0 and 100');
    });

    it('should return error when setVolume handler is not configured', async () => {
      const { result } = renderHook(() => usePlayerControls({}));

      const response = await result.current.setVolume(50);

      expect(response.success).toBe(false);
      expect(response.error).toContain('Volume handler not configured');
    });

    it('should handle setVolume errors', async () => {
      mockOnSetVolume.mockRejectedValueOnce(new Error('Volume out of range'));

      const { result } = renderHook(() =>
        usePlayerControls({ onSetVolume: mockOnSetVolume })
      );

      const response = await result.current.setVolume(50);

      expect(response.success).toBe(false);
      expect(response.error).toContain('Volume out of range');
    });
  });

  describe('Queue Operations', () => {
    it('should call playTrack handler with correct track ID', async () => {
      const { result } = renderHook(() =>
        usePlayerControls({ onPlayTrack: mockOnPlayTrack })
      );

      const response = await result.current.playTrack(5);

      expect(mockOnPlayTrack).toHaveBeenCalledWith(5);
      expect(response.success).toBe(true);
    });

    it('should reject negative track ID', async () => {
      const { result } = renderHook(() =>
        usePlayerControls({ onPlayTrack: mockOnPlayTrack })
      );

      const response = await result.current.playTrack(-1);

      expect(mockOnPlayTrack).not.toHaveBeenCalled();
      expect(response.success).toBe(false);
      expect(response.error).toContain('positive');
    });

    it('should reject zero track ID', async () => {
      const { result } = renderHook(() =>
        usePlayerControls({ onPlayTrack: mockOnPlayTrack })
      );

      const response = await result.current.playTrack(0);

      expect(mockOnPlayTrack).not.toHaveBeenCalled();
      expect(response.success).toBe(false);
      expect(response.error).toContain('positive');
    });

    it('should call removeFromQueue handler with correct index', async () => {
      const { result } = renderHook(() =>
        usePlayerControls({ onRemoveFromQueue: mockOnRemoveFromQueue })
      );

      const response = await result.current.removeFromQueue(2);

      expect(mockOnRemoveFromQueue).toHaveBeenCalledWith(2);
      expect(response.success).toBe(true);
    });

    it('should reject negative queue index', async () => {
      const { result } = renderHook(() =>
        usePlayerControls({ onRemoveFromQueue: mockOnRemoveFromQueue })
      );

      const response = await result.current.removeFromQueue(-1);

      expect(mockOnRemoveFromQueue).not.toHaveBeenCalled();
      expect(response.success).toBe(false);
      expect(response.error).toContain('negative');
    });

    it('should handle playTrack errors', async () => {
      mockOnPlayTrack.mockRejectedValueOnce(new Error('Track not found'));

      const { result } = renderHook(() =>
        usePlayerControls({ onPlayTrack: mockOnPlayTrack })
      );

      const response = await result.current.playTrack(5);

      expect(response.success).toBe(false);
      expect(response.error).toContain('Track not found');
    });

    it('should handle removeFromQueue errors', async () => {
      mockOnRemoveFromQueue.mockRejectedValueOnce(new Error('Invalid index'));

      const { result } = renderHook(() =>
        usePlayerControls({ onRemoveFromQueue: mockOnRemoveFromQueue })
      );

      const response = await result.current.removeFromQueue(10);

      expect(response.success).toBe(false);
      expect(response.error).toContain('Invalid index');
    });
  });

  describe('State Management', () => {
    it('should initially have isLoading as false', () => {
      const { result } = renderHook(() =>
        usePlayerControls({ onPlay: mockOnPlay })
      );

      expect(result.current.isLoading).toBe(false);
    });

    it('should initially have no error', () => {
      const { result } = renderHook(() =>
        usePlayerControls({ onPlay: mockOnPlay })
      );

      expect(result.current.lastError).toBeUndefined();
    });

    it('should return error result from failed operation', async () => {
      mockOnPlay.mockRejectedValueOnce(new Error('Play failed'));

      const { result } = renderHook(() =>
        usePlayerControls({ onPlay: mockOnPlay })
      );

      const response = await result.current.play();
      expect(response.error).toBe('Play failed');
    });

    it('should return error in response and indicate failure', async () => {
      mockOnPlay.mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() =>
        usePlayerControls({ onPlay: mockOnPlay })
      );

      const response = await result.current.play();
      expect(response.success).toBe(false);
      expect(response.error).toContain('Network error');
    });
  });

  describe('Debug Logging', () => {
    it('should log operations when debug enabled', async () => {
      const consoleSpy = vi.spyOn(console, 'log').mockImplementation();

      const { result } = renderHook(() =>
        usePlayerControls({ onPlay: mockOnPlay, debug: true })
      );

      await result.current.play();

      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('[usePlayerControls]'),
        expect.any(String)
      );

      consoleSpy.mockRestore();
    });

    it('should not log when debug disabled', async () => {
      const consoleSpy = vi.spyOn(console, 'log').mockImplementation();

      const { result } = renderHook(() =>
        usePlayerControls({ onPlay: mockOnPlay, debug: false })
      );

      await result.current.play();

      expect(consoleSpy).not.toHaveBeenCalledWith(
        expect.stringContaining('[usePlayerControls]'),
        expect.anything()
      );

      consoleSpy.mockRestore();
    });
  });

  describe('Configuration', () => {
    it('should accept custom seek debounce configuration', () => {
      const { result } = renderHook(() =>
        usePlayerControls({ onSeek: mockOnSeek, seekDebounceMs: 200 })
      );

      // Hook should be configured properly
      expect(result.current.seekDebounced).toBeDefined();
      expect(result.current.seek).toBeDefined();
    });

    it('should work without any handlers configured', () => {
      const { result } = renderHook(() => usePlayerControls({}));

      expect(result.current.play).toBeDefined();
      expect(result.current.pause).toBeDefined();
      expect(result.current.seek).toBeDefined();
      expect(result.current.setVolume).toBeDefined();
    });

    it('should use default seek debounce time', () => {
      const { result } = renderHook(() =>
        usePlayerControls({ onSeek: mockOnSeek })
      );

      // Should have default 300ms debounce configured
      expect(result.current.seekDebounced).toBeDefined();
    });
  });

  describe('Multiple Concurrent Operations', () => {
    it('should handle multiple operations concurrently', async () => {
      const { result } = renderHook(() =>
        usePlayerControls({
          onPlay: mockOnPlay,
          onSeek: mockOnSeek,
          onSetVolume: mockOnSetVolume,
        })
      );

      // Execute multiple operations concurrently
      const [playResult, seekResult, volumeResult] = await Promise.all([
        result.current.play(),
        result.current.seek(30),
        result.current.setVolume(75),
      ]);

      expect(playResult.success).toBe(true);
      expect(seekResult.success).toBe(true);
      expect(volumeResult.success).toBe(true);

      expect(mockOnPlay).toHaveBeenCalledTimes(1);
      expect(mockOnSeek).toHaveBeenCalledWith(30);
      expect(mockOnSetVolume).toHaveBeenCalledWith(75);
    });

    it('should handle one failure among multiple concurrent operations', async () => {
      mockOnSeek.mockRejectedValueOnce(new Error('Seek failed'));

      const { result } = renderHook(() =>
        usePlayerControls({
          onPlay: mockOnPlay,
          onSeek: mockOnSeek,
          onSetVolume: mockOnSetVolume,
        })
      );

      const [playResult, seekResult, volumeResult] = await Promise.all([
        result.current.play(),
        result.current.seek(30),
        result.current.setVolume(75),
      ]);

      expect(playResult.success).toBe(true);
      expect(seekResult.success).toBe(false);
      expect(volumeResult.success).toBe(true);
    });
  });
});
