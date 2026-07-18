/**
 * Player Redux Selectors
 * ~~~~~~~~~~~~~~~~~~~~~~
 *
 * Split out of store/selectors/index.ts (#4316).
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { createSelector } from '@reduxjs/toolkit';
import type { RootState } from '@/store/index';

const formatSeconds = (seconds: number): string => {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
};

/**
 * Basic selectors (non-memoized, for simple properties)
 */
export const playerSelectors = {
  selectIsPlaying: (state: RootState) => state.player.isPlaying,
  selectCurrentTrack: (state: RootState) => state.player.currentTrack,
  selectCurrentTime: (state: RootState) => state.player.currentTime,
  selectDuration: (state: RootState) => state.player.duration,
  selectVolume: (state: RootState) => state.player.volume,
  selectIsMuted: (state: RootState) => state.player.isMuted,
  selectPreset: (state: RootState) => state.player.preset,
  selectPlayerLoading: (state: RootState) => state.player.isLoading,
  selectPlayerError: (state: RootState) => state.player.error,
  /** Full streaming sub-state ({normal, enhanced}) */
  selectStreaming: (state: RootState) => state.player.streaming,
  /** Streaming state for the enhanced stream (idle | buffering | streaming | error | complete) */
  selectEnhancedStreamingState: (state: RootState) => state.player.streaming.enhanced.state,
};

export const selectPlaybackProgress = createSelector(
  [(state: RootState) => state.player.currentTime, (state: RootState) => state.player.duration],
  (currentTime, duration): number => (duration > 0 ? currentTime / duration : 0)
);

/**
 * @internal Recomputes every second because `currentTime` is an input. No
 * component subscribes to it today — do NOT call it directly from a component
 * (that would re-render at 1 Hz). Prefer formatting time at the leaf that needs
 * it. Kept only as part of the `optimizedSelectors` barrel (#4206).
 */
export const selectFormattedTime = createSelector(
  [(state: RootState) => state.player.currentTime, (state: RootState) => state.player.duration],
  (currentTime, duration) => ({
    current: formatSeconds(currentTime),
    total: formatSeconds(duration),
  })
);

/**
 * Complete playback state.
 *
 * @internal Recomputes every second because `currentTime` is an input (it
 * feeds `progress` and the formatted `currentTime`). No component subscribes to
 * it directly — it backs `selectAppSnapshot` and the `optimizedSelectors`
 * barrel. Do NOT subscribe a component to it directly or it will re-render at
 * 1 Hz; read the discrete fields you need from `playerSelectors` instead (#4206).
 */
export const selectPlaybackState = createSelector(
  [
    (state: RootState) => state.player.isPlaying,
    (state: RootState) => state.player.currentTrack,
    (state: RootState) => state.player.currentTime,
    (state: RootState) => state.player.duration,
    (state: RootState) => state.player.volume,
    (state: RootState) => state.player.isMuted,
    (state: RootState) => state.player.preset,
    (state: RootState) => state.connection.wsConnected,
    (state: RootState) => state.connection.apiConnected,
  ],
  (isPlaying, currentTrack, currentTime, duration, volume, isMuted, preset, wsConnected, apiConnected) => ({
    track: currentTrack,
    isPlaying,
    progress: duration > 0 ? currentTime / duration : 0,
    currentTime: formatSeconds(currentTime),
    duration: formatSeconds(duration),
    volume,
    isMuted,
    preset,
    canPlay: wsConnected && apiConnected && currentTrack !== null,
  })
);
