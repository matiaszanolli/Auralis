/**
 * usePlaybackState Hook Tests
 *
 * Tests for library playback state management:
 * - Redux-derived currentTrackId / isPlaying (single source of truth)
 * - handlePlayTrack delegates to the shared usePlayTrack hook (#3940)
 * - handlePlayPause delegates to the shared session toggle (#5514)
 *
 * (Rewritten for #3940: the hook now reads state from Redux and delegates the
 * play flow to usePlayTrack instead of taking an onTrackPlay callback, so the
 * tests render under a real <Provider> and assert delegation. The previous
 * suite predated the Redux usage and failed for lack of a Provider.
 * Rewritten for #5514: the raw WS `pause` sender is gone — the library view
 * toggles the shared session exactly like the transport bar.)
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

// handlePlayPause must be the transport bar's session toggle (#5514) — not a
// raw WS `pause` frame, which had no matching resume sender and stalled the
// backend stream mid-track.
const mockHandlePlayPause = vi.fn();
vi.mock('@/contexts/PlaybackSessionContext', () => ({
  usePlaybackControls: () => ({ handlePlayPause: mockHandlePlayPause }),
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

  describe('handlePlayPause', () => {
    it('delegates to the shared session toggle (#5514)', () => {
      const { wrapper } = makeWrapper();
      const { result } = renderHook(() => usePlaybackState(), { wrapper });

      act(() => {
        result.current.handlePlayPause();
      });

      expect(mockHandlePlayPause).toHaveBeenCalledTimes(1);
    });
  });

  describe('Handler memoization', () => {
    it('keeps handlePlayPause stable across rerenders', () => {
      const { wrapper } = makeWrapper();
      const { result, rerender } = renderHook(() => usePlaybackState(), { wrapper });

      const initialPause = result.current.handlePlayPause;
      rerender();

      expect(result.current.handlePlayPause).toBe(initialPause);
    });
  });
});
