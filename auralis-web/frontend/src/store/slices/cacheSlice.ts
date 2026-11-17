/**
 * Cache State Slice
 * ~~~~~~~~~~~~~~~~~
 *
 * Redux slice for managing cache state including:
 * - Cache statistics
 * - Cache health status
 * - Last update timestamp
 *
 * Phase C.3: Component Testing & Integration
 *
 * @copyright (C) 2024 Auralis Team
 * @license AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
 */

import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import type { CacheStats, CacheHealth } from '@/services/api/cacheShapeGuards';

export interface CacheState {
  stats: CacheStats | null;
  health: CacheHealth | null;
  lastUpdated: number;
}

const initialState: CacheState = {
  stats: null,
  health: null,
  lastUpdated: 0,
};

const cacheSlice = createSlice({
  name: 'cache',
  initialState,
  reducers: {
    /**
     * Set cache statistics
     */
    setCacheStats: {
      reducer(state, action: PayloadAction<CacheStats, string, { timestamp: number }>) {
        state.stats = action.payload;
        state.lastUpdated = action.meta.timestamp;
      },
      // #3623: strip per-track map before Redux storage so the slice size
      // stays bounded regardless of library size. Cache aggregates
      // (tier1/tier2/overall) are all the UI needs; per-track completion
      // belongs in a separate lazy API or component-local store.
      prepare(stats: CacheStats) {
        const stripped: CacheStats = {
          ...stats,
          tracks: {},
        };
        return { payload: stripped, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Set cache health
     */
    setCacheHealth: {
      reducer(state, action: PayloadAction<CacheHealth, string, { timestamp: number }>) {
        state.health = action.payload;
        state.lastUpdated = action.meta.timestamp;
      },
      prepare(health: CacheHealth) {
        return { payload: health, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Clear cache (local state after API call)
     */
    clearCacheLocal: {
      reducer(state, action: PayloadAction<void, string, { timestamp: number }>) {
        state.stats = {
          tier1: { chunks: 0, size_mb: 0, hits: 0, misses: 0, hit_rate: 0 },
          tier2: { chunks: 0, size_mb: 0, hits: 0, misses: 0, hit_rate: 0 },
          overall: {
            total_chunks: 0,
            total_size_mb: 0,
            total_hits: 0,
            total_misses: 0,
            overall_hit_rate: 0,
            tracks_cached: 0,
          },
          tracks: {},
        };
        state.lastUpdated = action.meta.timestamp;
      },
      prepare() {
        return { payload: undefined, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Reset cache state
     *
     * No production dispatch sites (#4921) — kept as an idiomatic
     * Redux action. Live sync uses field-level dispatches; see the note on
     * resetPlayer in playerSlice.ts for why the bulk-update siblings were
     * deleted rather than documented.
     */
    resetCache(state) {
      Object.assign(state, initialState);
    },
  },
});

export const {
  setCacheStats,
  setCacheHealth,
  clearCacheLocal,
  resetCache,
} = cacheSlice.actions;

// No selectors live here (#5129): none had a consumer, only same-named assertions in this
// slice's own test. A component reads a field straight off `state.cache`.

export default cacheSlice.reducer;
