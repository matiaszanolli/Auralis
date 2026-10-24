/**
 * Cross-Domain Redux Selectors
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Selectors and grouping objects that compose multiple domain selector
 * modules together. Split out of store/selectors/index.ts (#4316).
 *
 * @copyright (C) 2024 Auralis Team
 * @license AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
 */

import { createSelector } from '@reduxjs/toolkit';
import { playerSelectors, selectPlaybackProgress, selectFormattedTime, selectPlaybackState } from './player';
import {
  queueSelectors,
  selectCurrentQueueTrack,
  selectRemainingTime,
  selectQueueStats,
  selectQueueState,
} from './queue';
import { cacheSelectors, selectCacheMetrics, selectCacheHealthDerived } from './cache';
import { connectionSelectors, selectConnectionStatus } from './connection';

/**
 * Complete app state snapshot
 */
export const selectAppSnapshot = createSelector(
  [
    selectPlaybackState,
    selectQueueState,
    selectCacheMetrics,
    selectConnectionStatus,
  ],
  (playback, queue, cache, connection) => ({
    playback,
    queue,
    cache,
    connection,
  })
  // #5354: no isLoading/hasErrors aggregation — the underlying state never
  // changes, so the flags would be constant.
);

export const selectors = {
  player: playerSelectors,
  queue: queueSelectors,
  cache: cacheSelectors,
  connection: connectionSelectors,
  playback: selectPlaybackState,
  queueState: selectQueueState,
  appSnapshot: selectAppSnapshot,
};

/**
 * Grouped optimized selectors (all backed by Reselect createSelector).
 * Drop-in replacement for the former advanced.ts optimizedSelectors.
 */
export const optimizedSelectors = {
  player: {
    selectPlaybackProgress,
    selectFormattedTime,
    selectPlaybackState,
  },
  queue: {
    selectCurrentTrack: selectCurrentQueueTrack,
    selectRemainingTime,
    selectQueueStats,
    selectQueueState,
  },
  cache: {
    selectCacheMetrics,
    selectCacheHealth: selectCacheHealthDerived,
  },
  connection: {
    selectConnectionStatus,
  },
  appSnapshot: selectAppSnapshot,
};
