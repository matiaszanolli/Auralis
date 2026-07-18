/**
 * Cross-Domain Redux Selectors
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Selectors and grouping objects that compose multiple domain selector
 * modules together. Split out of store/selectors/index.ts (#4316).
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { createSelector } from '@reduxjs/toolkit';
import type { RootState } from '@/store/index';
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
    (state: RootState) => state.player.isLoading,
    (state: RootState) => state.queue.isLoading,
    (state: RootState) => state.cache.isLoading,
    (state: RootState) => state.player.error,
    (state: RootState) => state.queue.error,
    (state: RootState) => state.cache.error,
  ],
  (playback, queue, cache, connection, playerLoading, queueLoading, cacheLoading, playerError, queueError, cacheError) => ({
    playback,
    queue,
    cache,
    connection,
    isLoading: playerLoading || queueLoading || cacheLoading,
    hasErrors: !!(playerError || queueError || cacheError),
  })
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
