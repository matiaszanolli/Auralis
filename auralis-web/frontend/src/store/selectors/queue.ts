/**
 * Queue Redux Selectors
 * ~~~~~~~~~~~~~~~~~~~~~
 *
 * Split out of store/selectors/index.ts (#4316).
 *
 * @copyright (C) 2024 Auralis Team
 * @license AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
 */

import { createSelector } from '@reduxjs/toolkit';
import type { RootState } from '@/store/index';
import { formatHumanDuration } from '@/utils/timeFormat';

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

export const selectFormattedRemainingTime = createSelector(
  [selectRemainingTime],
  (remaining): { total: number; formatted: string } => ({
    total: remaining,
    formatted: formatHumanDuration(remaining),
  })
);
