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
 * @license GPLv3, see LICENSE for more details
 */

import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import type { CacheStats, CacheHealth } from '@/services/api/standardizedAPIClient';

export interface CacheState {
  stats: CacheStats | null;
  health: CacheHealth | null;
  isLoading: boolean;
  error: string | null;
  lastUpdated: number;
}

const initialState: CacheState = {
  stats: null,
  health: null,
  isLoading: false,
  error: null,
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
     * Set loading state
     */
    setIsLoading: {
      reducer(state, action: PayloadAction<boolean, string, { timestamp: number }>) {
        state.isLoading = action.payload;
        state.lastUpdated = action.meta.timestamp;
      },
      prepare(isLoading: boolean) {
        return { payload: isLoading, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Set error message
     */
    setError: {
      reducer(state, action: PayloadAction<string | null, string, { timestamp: number }>) {
        state.error = action.payload;
        state.lastUpdated = action.meta.timestamp;
      },
      prepare(error: string | null) {
        return { payload: error, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Clear error
     */
    clearError: {
      reducer(state, action: PayloadAction<void, string, { timestamp: number }>) {
        state.error = null;
        state.lastUpdated = action.meta.timestamp;
      },
      prepare() {
        return { payload: undefined, meta: { timestamp: Date.now() } };
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
  setIsLoading,
  setError,
  clearError,
  clearCacheLocal,
  resetCache,
} = cacheSlice.actions;

// Selectors
export const selectCacheStats = (state: { cache: CacheState }) => state.cache.stats;
export const selectCacheHealth = (state: { cache: CacheState }) => state.cache.health;
export const selectIsHealthy = (state: { cache: CacheState }) =>
  state.cache.health?.healthy ?? false;
export const selectIsLoading = (state: { cache: CacheState }) => state.cache.isLoading;
export const selectError = (state: { cache: CacheState }) => state.cache.error;

// #5212: selectOverallHitRate / selectTotalCacheSize / selectTotalChunks /
// selectTracksCached were deleted — no useSelector anywhere, only same-named
// assertions in this slice's own test. That was the second such batch in this
// file after #4395 cleared the first, so read this as a standing note: these
// slices have a habit of growing selectors ahead of any UI that needs them.
// Every field they projected is one property off `selectCacheStats`, which a
// component can read directly.

export default cacheSlice.reducer;
