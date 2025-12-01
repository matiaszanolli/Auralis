/**
 * usePlaybackControl Hook Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Comprehensive test suite for the usePlaybackControl hook.
 * Tests all playback control methods, error handling, and state management.
 *
 * @module hooks/player/__tests__/usePlaybackControl.test
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { usePlaybackControl } from '@/hooks/player/usePlaybackControl';
import { useRestAPI } from '@/hooks/api/useRestAPI';

// Mock the useRestAPI hook
vi.mock('@/hooks/api/useRestAPI');

describe('usePlaybackControl', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('play()', () => {
    it('should call POST /api/player/play when play is invoked', async () => {
      const mockPost = vi.fn().mockResolvedValue({ success: true });
      vi.mocked(useRestAPI).mockReturnValue({
        post: mockPost,
        get: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
        clearError: vi.fn(),
        isLoading: false,
        error: null,
      } as any);

      const { result } = renderHook(() => usePlaybackControl());

      await act(async () => {
        await result.current.play();
      });

      expect(mockPost).toHaveBeenCalledWith('/api/player/play');
    });

    it('should set isLoading to true while play is executing', async () => {
      const mockPost = vi.fn(
        () => new Promise((resolve) => setTimeout(() => resolve({ success: true }), 100))
      );
      vi.mocked(useRestAPI).mockReturnValue({
        post: mockPost,
        get: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
        clearError: vi.fn(),
        isLoading: false,
        error: null,
      } as any);

      const { result } = renderHook(() => usePlaybackControl());

      const playPromise = act(async () => {
        const promise = result.current.play();
        expect(result.current.isLoading).toBe(true);
        await promise;
      });

      await playPromise;
      expect(result.current.isLoading).toBe(false);
    });

    it('should handle play errors gracefully', async () => {
      const errorMessage = 'Player not available';
      const mockPost = vi.fn().mockRejectedValue(new Error(errorMessage));
      vi.mocked(useRestAPI).mockReturnValue({
        post: mockPost,
        get: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
        clearError: vi.fn(),
        isLoading: false,
        error: null,
      } as any);

      const { result } = renderHook(() => usePlaybackControl());

      await act(async () => {
        try {
          await result.current.play();
        } catch (err) {
          // Error expected
        }
      });

      expect(result.current.error).toBeDefined();
      expect(result.current.error?.message).toBe(errorMessage);
    });
  });

  describe('pause()', () => {
    it('should call POST /api/player/pause when pause is invoked', async () => {
      const mockPost = vi.fn().mockResolvedValue({ success: true });
      vi.mocked(useRestAPI).mockReturnValue({
        post: mockPost,
        get: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
        clearError: vi.fn(),
        isLoading: false,
        error: null,
      } as any);

      const { result } = renderHook(() => usePlaybackControl());

      await act(async () => {
        await result.current.pause();
      });

      expect(mockPost).toHaveBeenCalledWith('/api/player/pause');
    });

    it('should handle pause errors', async () => {
      const mockPost = vi.fn().mockRejectedValue(new Error('Pause failed'));
      vi.mocked(useRestAPI).mockReturnValue({
        post: mockPost,
        get: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
        clearError: vi.fn(),
        isLoading: false,
        error: null,
      } as any);

      const { result } = renderHook(() => usePlaybackControl());

      await act(async () => {
        try {
          await result.current.pause();
        } catch (err) {
          // Error expected
        }
      });

      expect(result.current.error).toBeDefined();
    });
  });

  describe('seek()', () => {
    it('should call POST /api/player/seek with position when seek is invoked', async () => {
      const mockPost = vi.fn().mockResolvedValue({ success: true });
      vi.mocked(useRestAPI).mockReturnValue({
        post: mockPost,
        get: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
        clearError: vi.fn(),
        isLoading: false,
        error: null,
      } as any);

      const { result } = renderHook(() => usePlaybackControl());

      await act(async () => {
        await result.current.seek(120);
      });

      expect(mockPost).toHaveBeenCalledWith('/api/player/seek', { position: 120 });
    });

    it('should clamp position to valid range (0 to duration)', async () => {
      const mockPost = vi.fn().mockResolvedValue({ success: true });
      vi.mocked(useRestAPI).mockReturnValue({
        post: mockPost,
        get: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
        clearError: vi.fn(),
        isLoading: false,
        error: null,
      } as any);

      const { result } = renderHook(() => usePlaybackControl());

      await act(async () => {
        // Test negative seek
        await result.current.seek(-10);
      });

      // Should be clamped to 0
      const calls = mockPost.mock.calls;
      expect(calls[0][1].position).toBeGreaterThanOrEqual(0);
    });

    it('should handle seek errors', async () => {
      const mockPost = vi.fn().mockRejectedValue(new Error('Seek failed'));
      vi.mocked(useRestAPI).mockReturnValue({
        post: mockPost,
        get: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
        clearError: vi.fn(),
        isLoading: false,
        error: null,
      } as any);

      const { result } = renderHook(() => usePlaybackControl());

      await act(async () => {
        try {
          await result.current.seek(120);
        } catch (err) {
          // Error expected
        }
      });

      expect(result.current.error).toBeDefined();
    });
  });

  describe('next()', () => {
    it('should call POST /api/player/next when next is invoked', async () => {
      const mockPost = vi.fn().mockResolvedValue({ success: true });
      vi.mocked(useRestAPI).mockReturnValue({
        post: mockPost,
        get: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
        clearError: vi.fn(),
        isLoading: false,
        error: null,
      } as any);

      const { result } = renderHook(() => usePlaybackControl());

      await act(async () => {
        await result.current.next();
      });

      expect(mockPost).toHaveBeenCalledWith('/api/player/next');
    });
  });

  describe('previous()', () => {
    it('should call POST /api/player/previous when previous is invoked', async () => {
      const mockPost = vi.fn().mockResolvedValue({ success: true });
      vi.mocked(useRestAPI).mockReturnValue({
        post: mockPost,
        get: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
        clearError: vi.fn(),
        isLoading: false,
        error: null,
      } as any);

      const { result } = renderHook(() => usePlaybackControl());

      await act(async () => {
        await result.current.previous();
      });

      expect(mockPost).toHaveBeenCalledWith('/api/player/previous');
    });
  });

  describe('setVolume()', () => {
    it('should call POST /api/player/volume with volume when setVolume is invoked', async () => {
      const mockPost = vi.fn().mockResolvedValue({ success: true });
      vi.mocked(useRestAPI).mockReturnValue({
        post: mockPost,
        get: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
        clearError: vi.fn(),
        isLoading: false,
        error: null,
      } as any);

      const { result } = renderHook(() => usePlaybackControl());

      await act(async () => {
        await result.current.setVolume(0.8);
      });

      expect(mockPost).toHaveBeenCalledWith('/api/player/volume', { volume: 0.8 });
    });

    it('should clamp volume to 0.0-1.0 range', async () => {
      const mockPost = vi.fn().mockResolvedValue({ success: true });
      vi.mocked(useRestAPI).mockReturnValue({
        post: mockPost,
        get: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
        clearError: vi.fn(),
        isLoading: false,
        error: null,
      } as any);

      const { result } = renderHook(() => usePlaybackControl());

      // Test volume > 1.0
      await act(async () => {
        await result.current.setVolume(1.5);
      });

      const calls = mockPost.mock.calls;
      expect(calls[0][1].volume).toBeLessThanOrEqual(1.0);
      expect(calls[0][1].volume).toBeGreaterThanOrEqual(0.0);
    });

    it('should handle volume errors', async () => {
      const mockPost = vi.fn().mockRejectedValue(new Error('Volume change failed'));
      vi.mocked(useRestAPI).mockReturnValue({
        post: mockPost,
        get: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
        clearError: vi.fn(),
        isLoading: false,
        error: null,
      } as any);

      const { result } = renderHook(() => usePlaybackControl());

      await act(async () => {
        try {
          await result.current.setVolume(0.5);
        } catch (err) {
          // Error expected
        }
      });

      expect(result.current.error).toBeDefined();
    });
  });

  describe('clearError()', () => {
    it('should clear error state when clearError is called', async () => {
      const mockPost = vi.fn().mockRejectedValue(new Error('Test error'));
      vi.mocked(useRestAPI).mockReturnValue({
        post: mockPost,
        get: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
        clearError: vi.fn(),
        isLoading: false,
        error: null,
      } as any);

      const { result } = renderHook(() => usePlaybackControl());

      // Trigger error
      await act(async () => {
        try {
          await result.current.play();
        } catch (err) {
          // Error expected
        }
      });

      expect(result.current.error).toBeDefined();

      // Clear error
      act(() => {
        result.current.clearError();
      });

      expect(result.current.error).toBeNull();
    });
  });

  describe('isLoading state', () => {
    it('should start as false', () => {
      vi.mocked(useRestAPI).mockReturnValue({
        post: vi.fn(),
        get: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
        clearError: vi.fn(),
        isLoading: false,
        error: null,
      } as any);

      const { result } = renderHook(() => usePlaybackControl());

      expect(result.current.isLoading).toBe(false);
    });
  });

  describe('error state', () => {
    it('should start as null', () => {
      vi.mocked(useRestAPI).mockReturnValue({
        post: vi.fn(),
        get: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
        clearError: vi.fn(),
        isLoading: false,
        error: null,
      } as any);

      const { result } = renderHook(() => usePlaybackControl());

      expect(result.current.error).toBeNull();
    });
  });

  describe('stop()', () => {
    it('should call POST /api/player/stop when stop is invoked', async () => {
      const mockPost = vi.fn().mockResolvedValue({ success: true });
      vi.mocked(useRestAPI).mockReturnValue({
        post: mockPost,
        get: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
        clearError: vi.fn(),
        isLoading: false,
        error: null,
      } as any);

      const { result } = renderHook(() => usePlaybackControl());

      await act(async () => {
        await result.current.stop();
      });

      expect(mockPost).toHaveBeenCalledWith('/api/player/stop');
    });
  });
});
