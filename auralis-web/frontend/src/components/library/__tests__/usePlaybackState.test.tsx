/**
 * usePlaybackState Hook Tests
 *
 * Tests for library playback state management:
 * - Redux-derived currentTrackId / isPlaying (single source of truth)
 * - handlePlayTrack delegates to the shared usePlayTrack hook (#3940)
 * - handlePause sends a pause WebSocket message
 *
 * (Rewritten for #3940: the hook now reads state from Redux and delegates the
 * play flow to usePlayTrack instead of taking an onTrackPlay callback, so the
 * tests render under a real <Provider> and assert delegation. The previous
 * suite predated the Redux usage and failed for lack of a Provider.)
 */

import React from 'react';
import { vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import playerReducer, {
  setCurrentTrack,
  setIsPlaying,
} from '@/store/slices/playerSlice';
import { usePlaybackState } from '../usePlaybackState';

// handlePlayTrack must delegate to usePlayTrack().playTrack (#3940).
const mockPlayTrack = vi.fn();
vi.mock('@/hooks/player/usePlayTrack', () => ({
  usePlayTrack: () => ({ playTrack: mockPlayTrack }),
}));

const mockWebSocketContext = {
  send: vi.fn(),
  subscribe: vi.fn(() => vi.fn()),
  unsubscribe: vi.fn(),
  isConnected: true,
};
vi.mock('@/contexts/WebSocketContext', () => ({
  useWebSocketContext: () => mockWebSocketContext,
  WebSocketProvider: ({ children }: { children: React.ReactNode }) => children,
}));

const mockTrack = {
  id: 1,
  title: 'Test Track',
  artist: 'Test Artist',
  album: 'Test Album',
  duration: 180,
  filepath: '/path/to/track.mp3',
};

const makeWrapper = () => {
  const store = configureStore({ reducer: { player: playerReducer } });
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <Provider store={store}>{children}</Provider>
  );
  return { store, wrapper };
};

describe('usePlaybackState', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Redux-derived state', () => {
    it('initializes with undefined currentTrackId and false isPlaying', () => {
      const { wrapper } = makeWrapper();
      const { result } = renderHook(() => usePlaybackState(), { wrapper });

      expect(result.current.currentTrackId).toBeUndefined();
      expect(result.current.isPlaying).toBe(false);
    });

    it('reflects the playing track from the Redux store', () => {
      const { store, wrapper } = makeWrapper();
      act(() => {
        store.dispatch(setCurrentTrack(mockTrack as never));
        store.dispatch(setIsPlaying(true));
      });

      const { result } = renderHook(() => usePlaybackState(), { wrapper });

      expect(result.current.currentTrackId).toBe(1);
      expect(result.current.isPlaying).toBe(true);
    });
  });

  describe('handlePlayTrack', () => {
    it('delegates to usePlayTrack().playTrack with the track', async () => {
      const { wrapper } = makeWrapper();
      const { result } = renderHook(() => usePlaybackState(), { wrapper });

      await act(async () => {
        await result.current.handlePlayTrack(mockTrack as never);
      });

      expect(mockPlayTrack).toHaveBeenCalledTimes(1);
      expect(mockPlayTrack).toHaveBeenCalledWith(mockTrack);
    });
  });

  describe('handlePause', () => {
    it('sends a pause WebSocket message', () => {
      const { wrapper } = makeWrapper();
      const { result } = renderHook(() => usePlaybackState(), { wrapper });

      act(() => {
        result.current.handlePause();
      });

      expect(mockWebSocketContext.send).toHaveBeenCalledWith({ type: 'pause' });
    });
  });

  describe('Handler memoization', () => {
    it('keeps handlePause stable across rerenders', () => {
      const { wrapper } = makeWrapper();
      const { result, rerender } = renderHook(() => usePlaybackState(), { wrapper });

      const initialPause = result.current.handlePause;
      rerender();

      expect(result.current.handlePause).toBe(initialPause);
    });
  });
});
