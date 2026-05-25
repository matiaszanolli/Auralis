/**
 * usePlaybackControl Hook Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Comprehensive test suite for the usePlaybackControl hook.
 * Tests all playback control methods, error handling, and state management.
 *
 * @module hooks/player/__tests__/usePlaybackControl.test
 */

import React from 'react';
import { renderHook, act } from '@testing-library/react';
import { vi } from 'vitest';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { usePlaybackControl } from '@/hooks/player/usePlaybackControl';
import playerReducer, {
  setCurrentTrack as setCurrentTrackAction,
  setCurrentTime as setCurrentTimeAction,
  setIsPlaying as setIsPlayingAction,
} from '@/store/slices/playerSlice';
import queueReducer, {
  setCurrentIndex as setCurrentIndexAction,
  setQueue as setQueueAction,
} from '@/store/slices/queueSlice';

// Stable send mock — must be the same reference across renders so that
// play's [send] dep does not trigger unnecessary recreation (#2354).
const mockSend = vi.fn();

// Mock WebSocketContext with vi.mock for proper hoisting
// vi.mock is hoisted to top of file, ensuring mock is applied before imports
vi.mock('@/contexts/WebSocketContext', () => ({
  useWebSocketContext: () => ({
    isConnected: true,
    connectionStatus: 'connected' as const,
    subscribe: vi.fn(() => () => {}),
    subscribeAll: vi.fn(() => () => {}),
    send: mockSend,
    connect: vi.fn(),
    disconnect: vi.fn(),
  }),
}));

// Mock useRestAPI for tests that need to override API behavior
// Default mock returns a functional API object
const mockPost = vi.fn().mockResolvedValue({ success: true });
vi.mock('@/hooks/api/useRestAPI', () => ({
  useRestAPI: () => ({
    post: mockPost,
    get: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    clearError: vi.fn(),
    isLoading: false,
    error: null,
  }),
}));

// Mock usePlaybackState — shape must match PlaybackState interface (fixes #3009)
vi.mock('@/hooks/player/usePlaybackState', () => ({
  usePlaybackState: () => ({
    currentTrack: {
      id: 123,
      title: 'Test Track',
      artist: 'Test Artist',
      album: 'Test Album',
      duration: 180,
      filepath: '/path/to/track.mp3',
    },
    isPlaying: false,
    volume: 80,
    position: 0,
    duration: 180,
    queue: [],
    queueIndex: -1,
    gaplessEnabled: true,
    crossfadeEnabled: true,
    crossfadeDuration: 3.0,
    isLoading: false,
    error: null,
  }),
}));

// Create a test store - current track is provided by mocked usePlaybackState
const createTestStore = () => {
  return configureStore({
    reducer: {
      player: playerReducer,
      queue: queueReducer,
    },
  });
};

// Wrapper component that provides Redux store
// WebSocketContext is mocked above
const createWrapper = () => {
  const store = createTestStore();
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(Provider, { store, children });
  };
};

describe('usePlaybackControl', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSend.mockReset();
  });

  describe('play()', () => {
    it('should call send with play_normal when play is invoked', async () => {
      const { result } = renderHook(() => usePlaybackControl(), { wrapper: createWrapper() });

      await act(async () => {
        await result.current.play();
      });

      expect(mockSend).toHaveBeenCalledWith({
        type: 'play_normal',
        data: { track_id: 123 },
      });
    });

    it('should set isLoading to false after play completes', async () => {
      const { result } = renderHook(() => usePlaybackControl(), { wrapper: createWrapper() });

      // play() is synchronous (just sends WebSocket message), so isLoading goes true->false quickly
      await act(async () => {
        await result.current.play();
      });

      expect(result.current.isLoading).toBe(false);
    });

    it('should handle play errors gracefully', async () => {
      const errorMessage = 'WebSocket send failed';
      // play() uses WebSocket send, so make it throw
      mockSend.mockImplementationOnce(() => {
        throw new Error(errorMessage);
      });

      const { result } = renderHook(() => usePlaybackControl(), { wrapper: createWrapper() });

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
    it('should call send with pause type when pause is invoked', async () => {
      const { result } = renderHook(() => usePlaybackControl(), { wrapper: createWrapper() });

      await act(async () => {
        await result.current.pause();
      });

      // pause() uses WebSocket send, not REST API
      expect(mockSend).toHaveBeenCalledWith({
        type: 'pause',
        data: {},
      });
    });

    it('should handle pause errors', async () => {
      // pause() uses send which doesn't throw in normal operation
      // This test verifies that if send throws, the error is captured
      mockSend.mockImplementationOnce(() => {
        throw new Error('Pause failed');
      });

      const { result } = renderHook(() => usePlaybackControl(), { wrapper: createWrapper() });

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
    it('should call POST /api/player/seek with position as query param', async () => {
      const { result } = renderHook(() => usePlaybackControl(), { wrapper: createWrapper() });

      await act(async () => {
        await result.current.seek(120);
      });

      // seek() uses api.post(url, undefined, queryParams) pattern
      expect(mockPost).toHaveBeenCalledWith('/api/player/seek', undefined, { position: 120 });
    });

    it('should clamp position to valid range (0 to duration)', async () => {
      const { result } = renderHook(() => usePlaybackControl(), { wrapper: createWrapper() });

      await act(async () => {
        // Test negative seek - should be clamped to 0
        await result.current.seek(-10);
      });

      // Third argument is the query params object
      const calls = mockPost.mock.calls;
      expect(calls[0][2].position).toBeGreaterThanOrEqual(0);
    });

    it('should handle seek errors', async () => {
      mockPost.mockRejectedValueOnce(new Error('Seek failed'));

      const { result } = renderHook(() => usePlaybackControl(), { wrapper: createWrapper() });

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
      const { result } = renderHook(() => usePlaybackControl(), { wrapper: createWrapper() });

      await act(async () => {
        await result.current.next();
      });

      expect(mockPost).toHaveBeenCalledWith('/api/player/next');
    });
  });

  describe('previous()', () => {
    it('should call POST /api/player/previous when previous is invoked', async () => {
      const { result } = renderHook(() => usePlaybackControl(), { wrapper: createWrapper() });

      await act(async () => {
        await result.current.previous();
      });

      expect(mockPost).toHaveBeenCalledWith('/api/player/previous');
    });
  });

  describe('setVolume()', () => {
    it('should call POST /api/player/volume with volume as query param (0-100 scale)', async () => {
      const { result } = renderHook(() => usePlaybackControl(), { wrapper: createWrapper() });

      await act(async () => {
        await result.current.setVolume(0.8);
      });

      // Implementation converts 0.0-1.0 to 0-100 scale and uses query params
      // 0.8 * 100 = 80
      expect(mockPost).toHaveBeenCalledWith('/api/player/volume', undefined, { volume: 80 });
    });

    it('should clamp volume to 0.0-1.0 range before converting to 0-100', async () => {
      const { result } = renderHook(() => usePlaybackControl(), { wrapper: createWrapper() });

      // Test volume > 1.0 - should be clamped to 1.0, then converted to 100
      await act(async () => {
        await result.current.setVolume(1.5);
      });

      const calls = mockPost.mock.calls;
      // Third argument is query params, volume should be clamped to 100 (1.0 * 100)
      expect(calls[0][2].volume).toBeLessThanOrEqual(100);
      expect(calls[0][2].volume).toBeGreaterThanOrEqual(0);
    });

    it('should handle volume errors', async () => {
      mockPost.mockRejectedValueOnce(new Error('Volume change failed'));

      const { result } = renderHook(() => usePlaybackControl(), { wrapper: createWrapper() });

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

  describe('stop()', () => {
    it('should send stop WS message and optimistically clear redux state', async () => {
      const wrapper = createWrapper();
      const { result } = renderHook(() => usePlaybackControl(), { wrapper });

      await act(async () => {
        await result.current.stop();
      });

      expect(mockSend).toHaveBeenCalledWith({ type: 'stop', data: {} });
    });

    it('rolls back redux state when send() throws (#3364)', async () => {
      // Pre-fix: stop() optimistically dispatched clearQueue() with no
      // rollback if the WS send threw — UI showed cleared queue while
      // the backend (presumably still playing) had the real queue. Now
      // the catch block restores the snapshot taken before the dispatch.

      // Seed the redux store with a non-empty queue + currentTrack so we
      // can verify the rollback restores it exactly.
      const { store, wrapper } = (() => {
        const s = createTestStore();
        s.dispatch(setQueueAction([
          { id: 1, title: 'A', filepath: '/a.mp3', duration: 100 } as any,
          { id: 2, title: 'B', filepath: '/b.mp3', duration: 200 } as any,
        ]));
        s.dispatch(setCurrentIndexAction(1));
        s.dispatch(setCurrentTrackAction({
          id: 2, title: 'B', filepath: '/b.mp3', duration: 200,
        } as any));
        s.dispatch(setIsPlayingAction(true));
        s.dispatch(setCurrentTimeAction(42));

        const W: React.FC<{ children: React.ReactNode }> = ({ children }) =>
          React.createElement(Provider, { store: s, children });
        return { store: s, wrapper: W };
      })();

      // Make send() throw the way a closed-socket .send(JSON.stringify(...)) would
      mockSend.mockImplementationOnce(() => {
        throw new Error('WebSocket is closed');
      });

      const { result } = renderHook(() => usePlaybackControl(), { wrapper });

      await act(async () => {
        try {
          await result.current.stop();
        } catch { /* expected — error is rethrown */ }
      });

      // Rollback: queue/currentTrack/transport state must be restored.
      const state = store.getState();
      expect(state.queue.tracks).toHaveLength(2);
      expect(state.queue.tracks[0].id).toBe(1);
      expect(state.queue.tracks[1].id).toBe(2);
      expect(state.queue.currentIndex).toBe(1);
      expect(state.player.currentTrack?.id).toBe(2);
      expect(state.player.isPlaying).toBe(true);
      expect(state.player.currentTime).toBe(42);

      // And the error was surfaced to the caller.
      expect(result.current.error).toBeDefined();
    });

    it('keeps redux cleared when send() succeeds', async () => {
      const { store, wrapper } = (() => {
        const s = createTestStore();
        s.dispatch(setQueueAction([
          { id: 1, title: 'A', filepath: '/a.mp3', duration: 100 } as any,
        ]));
        s.dispatch(setIsPlayingAction(true));
        const W: React.FC<{ children: React.ReactNode }> = ({ children }) =>
          React.createElement(Provider, { store: s, children });
        return { store: s, wrapper: W };
      })();

      // Default mockSend is a no-op (doesn't throw) — happy path.
      const { result } = renderHook(() => usePlaybackControl(), { wrapper });
      await act(async () => {
        await result.current.stop();
      });

      const state = store.getState();
      expect(state.queue.tracks).toHaveLength(0);
      expect(state.player.isPlaying).toBe(false);
      expect(state.player.currentTrack).toBeNull();
    });
  });

  describe('clearError()', () => {
    it('should clear error state when clearError is called', async () => {
      // Trigger an error by making seek() fail (seek uses REST API)
      mockPost.mockRejectedValueOnce(new Error('Test error'));

      const { result } = renderHook(() => usePlaybackControl(), { wrapper: createWrapper() });

      // Trigger error via seek (which uses REST API)
      await act(async () => {
        try {
          await result.current.seek(100);
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
      const { result } = renderHook(() => usePlaybackControl(), { wrapper: createWrapper() });

      expect(result.current.isLoading).toBe(false);
    });
  });

  describe('error state', () => {
    it('should start as null', () => {
      const { result } = renderHook(() => usePlaybackControl(), { wrapper: createWrapper() });

      expect(result.current.error).toBeNull();
    });
  });

  describe('play callback stability (#2354)', () => {
    it('play identity is stable across re-renders caused by new currentTrack object references', () => {
      // The usePlaybackState mock returns a new currentTrack object on every call
      // (arrow function with object literal), reproducing the position-update scenario
      // where Redux creates new object references at ~1/sec during playback.
      // Before the fix, play was in [send, playbackState.currentTrack] deps, so it
      // was recreated every render.  After the fix, only [send] remains as dep.
      const { result, rerender } = renderHook(() => usePlaybackControl(), {
        wrapper: createWrapper(),
      });

      const playRef1 = result.current.play;

      // Force a re-render — usePlaybackState mock will return a fresh object
      rerender();
      const playRef2 = result.current.play;

      rerender();
      const playRef3 = result.current.play;

      expect(playRef1).toBe(playRef2);
      expect(playRef2).toBe(playRef3);
    });

    it('play still works correctly after multiple re-renders (reads latest track via ref)', async () => {
      // Verify the ref-based approach does not lose the track ID across re-renders.
      // We assert that play() completes without error and leaves isLoading=false
      // (the hook reads currentTrack.id correctly via ref).
      const { result, rerender } = renderHook(() => usePlaybackControl(), {
        wrapper: createWrapper(),
      });

      rerender();
      rerender();

      await act(async () => {
        await result.current.play();
      });

      // No error means the track ID was available and the send() call succeeded
      expect(result.current.error).toBeNull();
      expect(result.current.isLoading).toBe(false);
    });
  });

  describe('stop()', () => {
    it('should call send with stop type when stop is invoked', async () => {
      const { result } = renderHook(() => usePlaybackControl(), { wrapper: createWrapper() });

      await act(async () => {
        await result.current.stop();
      });

      // stop() uses WebSocket send, not REST API
      expect(mockSend).toHaveBeenCalledWith({
        type: 'stop',
        data: {},
      });
    });
  });
});
