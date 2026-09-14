/**
 * Player Redux Hooks
 * ~~~~~~~~~~~~~~~~~~
 *
 * Player-slice state and action hooks. Split out of useReduxState.ts (#5239),
 * which re-exports everything here.
 *
 * @copyright (C) 2024 Auralis Team
 * @license AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
 */

import { useSelector, useDispatch, useStore, shallowEqual } from 'react-redux';
import { useCallback, useMemo } from 'react';
import type { RootState, AppDispatch } from '@/store';
import type { PlayerTrack } from '@/types/domain';
import * as playerActions from '@/store/slices/playerSlice';

/**
 * Access entire player state
 */
export const usePlayerState = () => {
  return useSelector((state: RootState) => state.player, shallowEqual);
};

/**
 * Access ONLY the player action callbacks — no state selectors.
 *
 * The returned object is stable across renders (every callback depends only on
 * the stable `dispatch`/`store` references), so action-only consumers don't
 * re-render on state changes. usePlayer() bundles `currentTime`, so it returns a
 * new object on every 1Hz position tick during playback; consumers that only
 * need callbacks (e.g. a context menu's "play") should use this instead to avoid
 * 1Hz render churn (#4176).
 */
export const usePlayerActions = () => {
  const dispatch = useDispatch<AppDispatch>();
  // store.getState() lets togglePlay read the live isPlaying at call time without
  // subscribing to it (which would re-render on every play/pause).
  const store = useStore<RootState>();

  const play = useCallback(() => dispatch(playerActions.setIsPlaying(true)), [dispatch]);
  const pause = useCallback(() => dispatch(playerActions.setIsPlaying(false)), [dispatch]);
  const togglePlay = useCallback(
    () => dispatch(playerActions.setIsPlaying(!store.getState().player.isPlaying)),
    [dispatch, store]
  );
  const seek = useCallback(
    (time: number) => dispatch(playerActions.setCurrentTime(time)),
    [dispatch]
  );
  const setVolume = useCallback(
    (vol: number) => dispatch(playerActions.setVolume(vol)),
    [dispatch]
  );
  const setMuted = useCallback(
    (muted: boolean) => dispatch(playerActions.setMuted(muted)),
    [dispatch]
  );
  const toggleMute = useCallback(() => dispatch(playerActions.toggleMute()), [dispatch]);
  const setPreset = useCallback(
    (p: playerActions.PresetName) => dispatch(playerActions.setPreset(p)),
    [dispatch]
  );
  const setTrack = useCallback(
    (track: PlayerTrack | null) => dispatch(playerActions.setCurrentTrack(track)),
    [dispatch]
  );

  return useMemo(() => ({
    play, pause, togglePlay, seek, setVolume, setMuted, toggleMute, setPreset, setTrack,
  }), [play, pause, togglePlay, seek, setVolume, setMuted, toggleMute, setPreset, setTrack]);
};

/**
 * Access player playback controls and state
 */
export const usePlayer = () => {
  // Reuse the stable action callbacks (#4176) so they're defined in one place.
  const actions = usePlayerActions();

  // Granular selectors — each only triggers a re-render when its specific field
  // changes, preventing the full player slice subscription from causing cascading
  // re-renders on every WebSocket position update (fixes #2537).
  const isPlaying = useSelector((state: RootState) => state.player.isPlaying);
  const currentTrack = useSelector((state: RootState) => state.player.currentTrack);
  const currentTime = useSelector((state: RootState) => state.player.currentTime);
  const duration = useSelector((state: RootState) => state.player.duration);
  const volume = useSelector((state: RootState) => state.player.volume);
  const isMuted = useSelector((state: RootState) => state.player.isMuted);
  const preset = useSelector((state: RootState) => state.player.preset);
  const isLoading = useSelector((state: RootState) => state.player.isLoading);
  const error = useSelector((state: RootState) => state.player.error);

  // Memoize the returned object so consumers only re-render when state they
  // actually use changes, not on every render of this hook (fixes #2537).
  return useMemo(() => ({
    isPlaying,
    currentTrack,
    currentTime,
    duration,
    volume,
    isMuted,
    preset,
    isLoading,
    error,
    ...actions,
  }), [
    isPlaying, currentTrack, currentTime, duration, volume, isMuted, preset,
    isLoading, error, actions,
  ]);
};

/**
 * Get current playback progress (0-1)
 */
export const usePlaybackProgress = () => {
  const currentTime = useSelector((state: RootState) => state.player.currentTime);
  const duration = useSelector((state: RootState) => state.player.duration);
  return duration > 0 ? currentTime / duration : 0;
};
