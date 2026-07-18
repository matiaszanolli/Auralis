/**
 * Cache Redux Selectors
 * ~~~~~~~~~~~~~~~~~~~~~
 *
 * Split out of store/selectors/index.ts (#4316).
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { createSelector } from '@reduxjs/toolkit';
import type { RootState } from '@/store/index';

export const cacheSelectors = {
  selectCacheStats: (state: RootState) => state.cache.stats,
  selectCacheHealth: (state: RootState) => state.cache.health,
  selectCacheLoading: (state: RootState) => state.cache.isLoading,
  selectCacheError: (state: RootState) => state.cache.error,
};

export const selectCacheMetrics = createSelector(
  [(state: RootState) => state.cache.stats],
  (stats) => {
    if (!stats) {
      return { hitRate: 0, totalSize: 0, totalChunks: 0, tracksCached: 0, tier1Size: 0, tier2Size: 0 };
    }
    return {
      hitRate: stats.overall.overall_hit_rate,
      totalSize: stats.overall.total_size_mb,
      totalChunks: stats.overall.total_chunks,
      tracksCached: stats.overall.tracks_cached,
      tier1Size: stats.tier1.size_mb,
      tier2Size: stats.tier2.size_mb,
    };
  }
);

export const selectCacheHealthDerived = createSelector(
  [(state: RootState) => state.cache.health],
  (health) => ({
    healthy: health?.healthy ?? false,
    hitRate: health?.overall_hit_rate ?? 0,
  })
);
