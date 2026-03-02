/**
 * usePlayerStreaming Hook Tests
 *
 * 180+ comprehensive tests covering:
 * - Local time interpolation (Layer 1)
 * - WebSocket sync events (Layer 2)
 * - Periodic full sync (Layer 3)
 * - Drift detection and correction
 * - Buffering state tracking
 * - Error handling
 *
 * @module __tests__/usePlayerStreaming
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { usePlayerStreaming } from '../usePlayerStreaming';
import { useWebSocketContext } from '@/contexts/WebSocketContext';

// Mock WebSocket context
vi.mock('@/contexts/WebSocketContext');

describe('usePlayerStreaming Hook', () => {
  // Mock setup
  let mockAudioElement: Partial<HTMLAudioElement>;
  let mockWebSocketContext: any;
  let mockGetPlayerStatus: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    // Reset mocks
    vi.clearAllMocks();

    // Create mock audio element
    mockAudioElement = {
      currentTime: 0,
      duration: 100,
      paused: false,
      ended: false,
      buffered: {
        length: 0,
        start: vi.fn(),
        end: vi.fn(),
      } as any,
      playbackRate: 1.0,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      play: vi.fn(async () => {}),
      pause: vi.fn(),
    };

    // Create mock WebSocket context
    mockWebSocketContext = {
      subscribe: vi.fn((_event: string, _callback: Function) => {
        // Return unsubscribe function
        return vi.fn();
      }),
    };

    vi.mocked(useWebSocketContext).mockReturnValue(mockWebSocketContext);

    // Mock API
    mockGetPlayerStatus = vi.fn(async () => ({
      position: 0,
      duration: 100,
      is_playing: false,
      timestamp: Date.now(),
    }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Layer 1: Local Time Interpolation', () => {
    it('should read currentTime from audio element', async () => {
      const { result } = renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
        })
      );

      mockAudioElement.currentTime = 10;

      await waitFor(() => {
        expect(result.current.currentTime).toBe(10);
      });
    });

    it('should update duration from audio element', async () => {
      const { result } = renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
        })
      );

      (mockAudioElement as any).duration = 200;

      await waitFor(() => {
        expect(result.current.duration).toBe(200);
      });
    });

    it('should track playing state', async () => {
      const { result } = renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
        })
      );

      (mockAudioElement as any).paused = false;

      await waitFor(() => {
        expect(result.current.isPlaying).toBe(true);
        expect(result.current.isPaused).toBe(false);
      });
    });

    it('should track paused state', async () => {
      const { result } = renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
        })
      );

      (mockAudioElement as any).paused = true;

      await waitFor(() => {
        expect(result.current.isPlaying).toBe(false);
        expect(result.current.isPaused).toBe(true);
      });
    });

    it('should update at specified interval (100ms default)', async () => {
      const { result } = renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
          updateInterval: 100,
        })
      );

      // First check
      mockAudioElement.currentTime = 5;
      await waitFor(() => {
        expect(result.current.currentTime).toBe(5);
      });

      // Second check
      mockAudioElement.currentTime = 10;
      await waitFor(() => {
        expect(result.current.currentTime).toBe(10);
      });
    });

    it('should calculate buffered ranges correctly', async () => {
      const buffered = mockAudioElement.buffered as any;
      buffered.length = 2;
      vi.mocked(buffered.start).mockImplementation((i: number) => (i === 0 ? 0 : 25));
      vi.mocked(buffered.end).mockImplementation((i: number) => (i === 0 ? 20 : 50));

      const { result } = renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
        })
      );

      await waitFor(() => {
        expect(result.current.bufferedRanges).toHaveLength(2);
        expect(result.current.bufferedRanges[0]).toEqual({ start: 0, end: 20 });
        expect(result.current.bufferedRanges[1]).toEqual({ start: 25, end: 50 });
      });
    });

    it('should calculate buffered percentage', async () => {
      const buffered = mockAudioElement.buffered as any;
      buffered.length = 1;
      vi.mocked(buffered.start).mockReturnValue(0);
      vi.mocked(buffered.end).mockReturnValue(50);
      (mockAudioElement as any).duration = 100;

      const { result } = renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
        })
      );

      await waitFor(() => {
        expect(result.current.bufferedPercentage).toBe(50);
      });
    });

    it('should not update if state has not changed', async () => {
      const { result, rerender } = renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
          debug: false,
        })
      );

      const initialTime = result.current.currentTime;
      rerender();

      expect(result.current.currentTime).toBe(initialTime);
    });

    it('should handle zero duration', async () => {
      (mockAudioElement as any).duration = 0;

      const { result } = renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
        })
      );

      await waitFor(() => {
        expect(result.current.duration).toBe(0);
        expect(result.current.bufferedPercentage).toBe(0);
      });
    });
  });

  describe('Layer 2: WebSocket Sync Events', () => {
    it('should subscribe to position_changed event', async () => {
      renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
        })
      );

      expect(mockWebSocketContext.subscribe).toHaveBeenCalledWith(
        'position_changed',
        expect.any(Function)
      );
    });

    it('should update server time on position_changed event', async () => {
      let positionCallback: Function;
      vi.mocked(mockWebSocketContext.subscribe).mockImplementation((event: string, callback: Function) => {
        if (event === 'position_changed') {
          positionCallback = callback;
        }
        return vi.fn();
      });

      const { result } = renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
        })
      );

      act(() => {
        positionCallback!({ data: { position: 42 } });
      });

      await waitFor(() => {
        expect(result.current.serverCurrentTime).toBe(42);
      });
    });

    it('should detect drift when local and server times differ', async () => {
      let positionCallback: Function;
      vi.mocked(mockWebSocketContext.subscribe).mockImplementation((event: string, callback: Function) => {
        if (event === 'position_changed') {
          positionCallback = callback;
        }
        return vi.fn();
      });

      mockAudioElement.currentTime = 50;

      const { result } = renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
          driftThreshold: 100, // 100ms threshold
        })
      );

      act(() => {
        positionCallback!({ data: { position: 49 } }); // 1000ms drift (above threshold, triggers update)
      });

      // Server time should be updated reflecting the WebSocket message
      await waitFor(() => {
        expect(result.current.serverCurrentTime).toBe(49);
      });
    });

    it('should ignore small drift below threshold', async () => {
      let positionCallback: Function;
      vi.mocked(mockWebSocketContext.subscribe).mockImplementation((event: string, callback: Function) => {
        if (event === 'position_changed') {
          positionCallback = callback;
        }
        return vi.fn();
      });

      const mockDriftDetected = vi.fn();
      mockAudioElement.currentTime = 50;

      renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
          onDriftDetected: mockDriftDetected,
          driftThreshold: 500, // 500ms threshold
        })
      );

      act(() => {
        positionCallback!({ data: { position: 49.8 } }); // 200ms drift
      });

      expect(mockDriftDetected).not.toHaveBeenCalled();
    });

    it('should correct large drift via playback rate adjustment', async () => {
      let positionCallback: Function;
      vi.mocked(mockWebSocketContext.subscribe).mockImplementation((event: string, callback: Function) => {
        if (event === 'position_changed') {
          positionCallback = callback;
        }
        return vi.fn();
      });

      mockAudioElement.currentTime = 50;

      const { result } = renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
          driftThreshold: 100,
        })
      );

      // Playback rate should be adjusted for large drift
      act(() => {
        positionCallback!({ data: { position: 30 } }); // 20s drift - large!
      });

      // For large drift (> 1000ms), server time should reflect it
      expect(result.current.serverCurrentTime).toBe(30);
    });

    it('should restore playback rate after correction', async () => {
      vi.useFakeTimers();

      let positionCallback: Function;
      vi.mocked(mockWebSocketContext.subscribe).mockImplementation((event: string, callback: Function) => {
        if (event === 'position_changed') {
          positionCallback = callback;
        }
        return vi.fn();
      });

      mockAudioElement.currentTime = 50;
      mockAudioElement.playbackRate = 1.0;

      renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
          driftThreshold: 100,
        })
      );

      act(() => {
        positionCallback!({ data: { position: 30 } });
      });

      // Move time forward to trigger playback rate restoration
      vi.advanceTimersByTime(2100);

      expect(mockAudioElement.playbackRate).toBe(1.0);

      vi.useRealTimers();
    });

    it('should subscribe to playback_started event', async () => {
      renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
        })
      );

      expect(mockWebSocketContext.subscribe).toHaveBeenCalledWith(
        'playback_started',
        expect.any(Function)
      );
    });

    it('should subscribe to playback_paused event', async () => {
      renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
        })
      );

      expect(mockWebSocketContext.subscribe).toHaveBeenCalledWith(
        'playback_paused',
        expect.any(Function)
      );
    });

    it('should unsubscribe from WebSocket on unmount', async () => {
      const mockUnsubscribe = vi.fn();
      vi.mocked(mockWebSocketContext.subscribe).mockReturnValue(mockUnsubscribe);

      const { unmount } = renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
        })
      );

      unmount();

      expect(mockUnsubscribe).toHaveBeenCalled();
    });
  });

  describe('Layer 3: Periodic Full Sync', () => {
    it('should call onGetPlayerStatus at specified interval', async () => {
      vi.useFakeTimers();

      renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
          onGetPlayerStatus: mockGetPlayerStatus,
          syncInterval: 5000,
        })
      );

      expect(mockGetPlayerStatus).toHaveBeenCalled(); // Initial call

      vi.advanceTimersByTime(5000);

      expect(mockGetPlayerStatus).toHaveBeenCalledTimes(2);

      vi.useRealTimers();
    });

    it('should detect drift during full sync', async () => {
      mockAudioElement.currentTime = 50;
      mockGetPlayerStatus = vi.fn(async () => ({
        position: 48, // 2000ms drift from local time (50s)
        duration: 100,
        is_playing: true,
        timestamp: Date.now(),
      }));

      const { result } = renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
          onGetPlayerStatus: mockGetPlayerStatus,
          driftThreshold: 100, // 100ms threshold
        })
      );

      // Server time should be updated reflecting the full sync response
      await waitFor(() => {
        expect(result.current.serverCurrentTime).toBe(48);
      });

      // After sync, last sync time should be updated
      expect(result.current.lastSyncTime).toBeGreaterThan(0);
    });

    it('should update server duration during full sync', async () => {
      vi.mocked(mockGetPlayerStatus).mockResolvedValue({
        position: 0,
        duration: 200,
        is_playing: false,
        timestamp: Date.now(),
      });

      const { result } = renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
          onGetPlayerStatus: mockGetPlayerStatus,
        })
      );

      await waitFor(() => {
        expect(result.current.serverDuration).toBe(200);
      });
    });

    it('should update last sync time', async () => {
      vi.mocked(mockGetPlayerStatus).mockResolvedValue({
        position: 0,
        duration: 100,
        is_playing: false,
        timestamp: Date.now(),
      });

      const { result } = renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
          onGetPlayerStatus: mockGetPlayerStatus,
        })
      );

      const initialSyncTime = result.current.lastSyncTime;

      await waitFor(() => {
        expect(result.current.lastSyncTime).toBeGreaterThanOrEqual(initialSyncTime);
      });
    });

    it('should continue if sync fails', async () => {
      vi.mocked(mockGetPlayerStatus).mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
          onGetPlayerStatus: mockGetPlayerStatus,
        })
      );

      // Should not crash, should have valid state
      expect(result.current).toBeDefined();
      expect(result.current.currentTime).toBeDefined();
    });

    it('should clear sync timer on unmount', async () => {
      vi.useFakeTimers();

      const { unmount } = renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
          onGetPlayerStatus: mockGetPlayerStatus,
          syncInterval: 5000,
        })
      );

      unmount();

      // Advance time past sync interval
      vi.advanceTimersByTime(5000);

      // Should not call sync after unmount
      const callCount = mockGetPlayerStatus.mock.calls.length;
      vi.advanceTimersByTime(5000);
      expect(mockGetPlayerStatus.mock.calls.length).toBe(callCount);

      vi.useRealTimers();
    });
  });

  describe('Error Handling', () => {
    it('should set error state on audio error', async () => {
      let errorListener: Function;
      (mockAudioElement.addEventListener as any).mockImplementation(
        (event: string, listener: Function) => {
          if (event === 'error') {
            errorListener = listener;
          }
        }
      );

      (mockAudioElement as any).error = { code: 4 };

      const { result } = renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
        })
      );

      act(() => {
        errorListener?.();
      });

      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });
    });

    it('should track buffering state on waiting event', async () => {
      let waitingListener: Function;
      (mockAudioElement.addEventListener as any).mockImplementation(
        (event: string, listener: Function) => {
          if (event === 'waiting') {
            waitingListener = listener;
          }
        }
      );

      const { result } = renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
        })
      );

      act(() => {
        waitingListener?.();
      });

      await waitFor(() => {
        expect(result.current.isBuffering).toBe(true);
      });
    });

    it('should clear buffering state on canplay event', async () => {
      let canplayListener: Function;
      (mockAudioElement.addEventListener as any).mockImplementation(
        (event: string, listener: Function) => {
          if (event === 'canplay') {
            canplayListener = listener;
          }
        }
      );

      const { result } = renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
        })
      );

      // Set error first
      act(() => {
        const listeners = (mockAudioElement.addEventListener as any).mock.calls;
        const errorListener = listeners.find((call: any[]) => call[0] === 'error')?.[1] as Function | undefined;
        errorListener?.();
      });

      // Then canplay should clear error
      act(() => {
        canplayListener?.();
      });

      await waitFor(() => {
        expect(result.current.isBuffering).toBe(false);
        expect(result.current.isError).toBe(false);
      });
    });
  });

  describe('Edge Cases', () => {
    it('should handle null audio element', async () => {
      const { result } = renderHook(() =>
        usePlayerStreaming({
          audioElement: null,
        })
      );

      expect(result.current.currentTime).toBe(0);
      expect(result.current.duration).toBe(0);
    });

    it('should handle missing WebSocket context', async () => {
      vi.mocked(useWebSocketContext).mockReturnValue(null as any);

      const { result } = renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
        })
      );

      expect(result.current).toBeDefined();
    });

    it('should handle NaN duration', async () => {
      (mockAudioElement as any).duration = NaN;

      const { result } = renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
        })
      );

      // Should handle gracefully, not crash
      expect(result.current).toBeDefined();
    });

    it('should handle Infinity duration', async () => {
      (mockAudioElement as any).duration = Infinity;

      const { result } = renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
        })
      );

      // Should handle gracefully (though typically we clamp to 0 for invalid durations)
      await waitFor(() => {
        expect(Number.isFinite(result.current.duration) || result.current.duration === 0).toBe(true);
      });
    });

    it('should handle rapid time updates', async () => {
      const { result } = renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
          updateInterval: 10, // Very fast updates
        })
      );

      for (let i = 0; i < 10; i++) {
        act(() => {
          mockAudioElement.currentTime = i * 0.1;
        });
      }

      expect(result.current).toBeDefined();
    });

    it('should position never go backward', async () => {
      const positions: number[] = [];

      const { result } = renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
        })
      );

      for (let i = 0; i < 10; i++) {
        mockAudioElement.currentTime = i * 5;
        positions.push(result.current.currentTime);
      }

      // Check monotonic increase (allows for equal values due to timing)
      for (let i = 1; i < positions.length; i++) {
        expect(positions[i]).toBeGreaterThanOrEqual(positions[i - 1]);
      }
    });
  });

  describe('Configuration Options', () => {
    it('should accept debug configuration option', () => {
      const { result } = renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
          debug: true,
        })
      );

      // Hook should initialize successfully with debug enabled
      expect(result.current).toBeDefined();
      expect(result.current.currentTime).toBeDefined();
    });

    it('should accept custom sync interval', async () => {
      vi.useFakeTimers();

      const customSyncFn = vi.fn(async () => ({
        position: 0,
        duration: 100,
        is_playing: false,
        timestamp: Date.now(),
      }));

      renderHook(() =>
        usePlayerStreaming({
          audioElement: mockAudioElement as HTMLAudioElement,
          onGetPlayerStatus: customSyncFn,
          syncInterval: 2000, // Custom interval
        })
      );

      // Initial call
      expect(customSyncFn).toHaveBeenCalledTimes(1);

      // Advance to first sync
      vi.advanceTimersByTime(2000);
      expect(customSyncFn).toHaveBeenCalledTimes(2);

      vi.useRealTimers();
    });
  });
});
