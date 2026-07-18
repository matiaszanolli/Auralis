/**
 * Queue Redux Selectors
 * ~~~~~~~~~~~~~~~~~~~~~
 *
 * Split out of store/selectors/index.ts (#4316).
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { createSelector } from '@reduxjs/toolkit';
import type { QueueTrack } from '@/types/domain';
import type { RootState } from '@/store/index';

export const queueSelectors = {
  selectQueueTracks: (state: RootState) => state.queue.tracks,
  selectCurrentIndex: (state: RootState) => state.queue.currentIndex,
  selectQueueLoading: (state: RootState) => state.queue.isLoading,
  selectQueueError: (state: RootState) => state.queue.error,
};

export const selectCurrentQueueTrack = createSelector(
  [(state: RootState) => state.queue.tracks, (state: RootState) => state.queue.currentIndex],
  (tracks, currentIndex) => tracks[currentIndex] || null
);

export const selectRemainingTime = createSelector(
  [(state: RootState) => state.queue.tracks, (state: RootState) => state.queue.currentIndex],
  (tracks, currentIndex): number =>
    tracks.slice(currentIndex + 1).reduce((sum, track) => sum + track.duration, 0)
);

export const selectTotalQueueTime = createSelector(
  [(state: RootState) => state.queue.tracks],
  (tracks): number => tracks.reduce((sum, track) => sum + track.duration, 0)
);

export const selectFormattedQueueTime = createSelector(
  [selectTotalQueueTime],
  (total): string => {
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
  }
);

export const selectFormattedRemainingTime = createSelector(
  [selectRemainingTime],
  (remaining): { total: number; formatted: string } => {
    const hours = Math.floor(remaining / 3600);
    const minutes = Math.floor((remaining % 3600) / 60);
    const seconds = remaining % 60;
    return {
      total: remaining,
      formatted: hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m ${seconds}s`,
    };
  }
);

export const selectQueueStats = createSelector(
  [(state: RootState) => state.queue.tracks, (state: RootState) => state.queue.currentIndex],
  (tracks, currentIndex) => {
    const totalTime = tracks.reduce((sum, track) => sum + track.duration, 0);
    return {
      length: tracks.length,
      totalTime,
      averageTrackLength: tracks.length > 0 ? totalTime / tracks.length : 0,
      currentPosition: currentIndex,
    };
  }
);

/**
 * Complete queue state
 */
// #3620: compose existing memoized sub-selectors (selectRemainingTime,
// selectTotalQueueTime) instead of recomputing O(n) reductions inline.
// Same logic, but each cost is paid once globally and cached separately.
export const selectQueueState = createSelector(
  [
    (state: RootState) => state.queue.tracks,
    (state: RootState) => state.queue.currentIndex,
    selectRemainingTime,
    selectTotalQueueTime,
  ],
  (tracks, currentIndex, remainingTime, totalTime) => {
    const currentTrack = tracks[currentIndex] || null;
    return {
      tracks,
      currentIndex,
      currentTrack,
      length: tracks.length,
      hasNext: currentIndex < tracks.length - 1,
      hasPrevious: currentIndex > 0,
      remainingTime,
      totalTime,
      isEmpty: tracks.length === 0,
    };
  }
);

// ============================================================================
// Factory Selectors (for dynamic parameters — must use useMemo in components)
// ============================================================================

/**
 * Select track at specific index.
 * Usage: const selector = useMemo(() => makeSelectTrackAtIndex(idx), [idx]);
 */
export const makeSelectTrackAtIndex = (index: number) =>
  createSelector([(state: RootState) => state.queue.tracks], (tracks) => tracks[index] || null);

/**
 * Select tracks in range.
 * Usage: const selector = useMemo(() => makeSelectTracksInRange(s, e), [s, e]);
 */
export const makeSelectTracksInRange = (start: number, end: number) =>
  createSelector([(state: RootState) => state.queue.tracks], (tracks) => tracks.slice(start, end));

/**
 * Filter tracks by criteria.
 * Usage: const selector = useMemo(() => makeSelectFilteredTracks(pred), [pred]);
 */
export const makeSelectFilteredTracks = (predicate: (track: QueueTrack) => boolean) =>
  createSelector([(state: RootState) => state.queue.tracks], (tracks) => tracks.filter(predicate));

/**
 * Select tracks by duration range.
 * Usage: const selector = useMemo(() => makeSelectTracksByDuration(min, max), [min, max]);
 */
export const makeSelectTracksByDuration = (minSeconds: number, maxSeconds: number) =>
  createSelector([(state: RootState) => state.queue.tracks], (tracks) =>
    tracks.filter((track) => track.duration >= minSeconds && track.duration <= maxSeconds)
  );
