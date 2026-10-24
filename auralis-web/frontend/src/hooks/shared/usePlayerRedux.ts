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
 * re-render on state changes. Consumers that only need callbacks (e.g. a
 * context menu's "play") should use this; anything subscribing to player
 * state should read granular fields via usePlayerState or per-field
 * useSelector (#4176 — a convenience bundle of all player state re-rendered
 * on every 1Hz position tick).
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

  return useMemo(() => ({
    play, pause, togglePlay, seek, setVolume, setMuted, toggleMute, setPreset,
  }), [play, pause, togglePlay, seek, setVolume, setMuted, toggleMute, setPreset]);
};

// No usePlayer() umbrella hook (#5354): the isLoading/error fields it would
// surface never change, because nothing dispatches actions that change them.
