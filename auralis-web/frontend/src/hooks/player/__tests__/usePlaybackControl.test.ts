/**
 * usePlaybackControl Hook Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Comprehensive test suite for the usePlaybackControl hook.
 * Tests all playback control methods, error handling, and state management.
 *
 * @module hooks/player/__tests__/usePlaybackControl.test
 */

import { FC, ReactNode, createElement } from 'react';
import { renderHook, act } from '@testing-library/react';
import { vi } from 'vitest';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { usePlaybackControl } from '@/hooks/player/usePlaybackControl';
import playerReducer, {
  setCurrentTrack as setCurrentTrackAction,
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

// (Removed stale vi.mock for '@/hooks/player/usePlaybackState' — that
// module was deleted in #3126 as dead WS-shadow state. usePlaybackControl
// reads player state via Redux selectors; tests provide state through the
// test store below.)

const createTestStore = () => {
  return configureStore({
    reducer: {
      player: playerReducer,
      queue: queueReducer,
    },
  });
};

// #3580: default to seeding the store with a current track + queue entry so
// play()/seek()/setVolume() tests don't immediately throw "No track selected".
// Tests that need to verify the no-track path can pass `seedTrack: null`.
const DEFAULT_SEED_TRACK = {
  id: 123,
  title: 'Test Track',
  artist: 'Test Artist',
  album: 'Test Album',
  duration: 240,
};

// Wrapper component that provides Redux store
// WebSocketContext is mocked above
const createWrapper = (opts?: {
  seedTrack?: typeof DEFAULT_SEED_TRACK | null;
}) => {
  const store = createTestStore();
  const seed = opts?.seedTrack === undefined ? DEFAULT_SEED_TRACK : opts.seedTrack;
  if (seed) {
    store.dispatch(setCurrentTrackAction(seed));
    store.dispatch(setQueueAction([seed]));
    store.dispatch(setCurrentIndexAction(0));
  }
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(Provider, { store, children });
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

    it('should throw "No track selected" when no current track is set (#4479)', async () => {
      // Drive the guard at usePlaybackControl.ts:138-140 via the documented
      // seedTrack: null harness option — no current track, no queue.
      const { result } = renderHook(() => usePlaybackControl(), {
        wrapper: createWrapper({ seedTrack: null }),
      });

      await act(async () => {
        await expect(result.current.play()).rejects.toThrow('No track selected');
      });

      // Guard rejects before any WebSocket message is sent.
      expect(mockSend).not.toHaveBeenCalled();
      expect(result.current.error).toBeDefined();
      expect(result.current.error?.message).toBe('No track selected. Set queue first.');
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

      // seek() uses api.post(url, body) — JSON body, not query params
      expect(mockPost).toHaveBeenCalledWith('/api/player/seek', { position: 120 });
    });

    it('should clamp position to valid range (0 to duration)', async () => {
      const { result } = renderHook(() => usePlaybackControl(), { wrapper: createWrapper() });

      await act(async () => {
        // Test negative seek - should be clamped to 0
        await result.current.seek(-10);
      });

      // Second argument is the JSON body { position }
      const calls = mockPost.mock.calls;
      expect(calls[0][1].position).toBeGreaterThanOrEqual(0);
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

      // Implementation converts 0.0-1.0 to 0-100 scale and sends as JSON body
      // 0.8 * 100 = 80
      expect(mockPost).toHaveBeenCalledWith('/api/player/volume', { volume: 80 });
    });

    it('should clamp volume to 0.0-1.0 range before converting to 0-100', async () => {
      const { result } = renderHook(() => usePlaybackControl(), { wrapper: createWrapper() });

      // Test volume > 1.0 - should be clamped to 1.0, then converted to 100
      await act(async () => {
        await result.current.setVolume(1.5);
      });

      const calls = mockPost.mock.calls;
      // Second argument is the JSON body { volume }, clamped to 0-100
      expect(calls[0][1].volume).toBeLessThanOrEqual(100);
      expect(calls[0][1].volume).toBeGreaterThanOrEqual(0);
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

    // NOTE: the former 'rolls back redux state when send() throws' test was
    // removed in #3966 — send() is fire-and-forget and never throws, so the
    // rollback catch block it exercised was unreachable dead code and has been
    // deleted from stop(). The optimistic clear is now unconditional.

    it('keeps redux cleared when send() succeeds', async () => {
      const { store, wrapper } = (() => {
        const s = createTestStore();
        s.dispatch(setQueueAction([
          { id: 1, title: 'A', filepath: '/a.mp3', duration: 100 } as any,
        ]));
        s.dispatch(setIsPlayingAction(true));
        const W: FC<{ children: ReactNode }> = ({ children }) =>
          createElement(Provider, { store: s, children });
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

  describe('return identity (#4438)', () => {
    it('returns a stable object across re-renders when inputs are unchanged', () => {
      const { result, rerender } = renderHook(() => usePlaybackControl(), {
        wrapper: createWrapper(),
      });

      const first = result.current;
      rerender();
      // Memoized return: consumers using it in dependency arrays (e.g.
      // ComfortableApp's keyboard-shortcut registration) do not churn.
      expect(Object.is(result.current, first)).toBe(true);
    });
  });
});
