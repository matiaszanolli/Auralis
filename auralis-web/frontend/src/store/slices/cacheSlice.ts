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
  lastUpdate: number;
}

const initialState: CacheState = {
  stats: null,
  health: null,
  isLoading: false,
  error: null,
  lastUpdate: 0,
};

const cacheSlice = createSlice({
  name: 'cache',
  initialState,
  reducers: {
    /**
     * Set cache statistics
     */
    setCacheStats(state, action: PayloadAction<CacheStats>) {
      state.stats = action.payload;
      state.lastUpdate = Date.now();
    },

    /**
     * Set cache health
     */
    setCacheHealth(state, action: PayloadAction<CacheHealth>) {
      state.health = action.payload;
      state.lastUpdate = Date.now();
    },

    /**
     * Update both stats and health
     */
    updateCache(
      state,
      action: PayloadAction<{
        stats?: CacheStats;
        health?: CacheHealth;
      }>
    ) {
      if (action.payload.stats) {
        state.stats = action.payload.stats;
      }
      if (action.payload.health) {
        state.health = action.payload.health;
      }
      state.lastUpdate = Date.now();
    },

    /**
     * Set loading state
     */
    setIsLoading(state, action: PayloadAction<boolean>) {
      state.isLoading = action.payload;
    },

    /**
     * Set error message
     */
    setError(state, action: PayloadAction<string | null>) {
      state.error = action.payload;
    },

    /**
     * Clear error
     */
    clearError(state) {
      state.error = null;
    },

    /**
     * Clear cache (local state after API call)
     */
    clearCacheLocal(state) {
      state.stats = {
        ...initialState.stats,
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
      } as CacheStats;
      state.lastUpdate = Date.now();
    },

    /**
     * Reset cache state
     */
    resetCache(state) {
      Object.assign(state, initialState);
    },
  },
});

export const {
  setCacheStats,
  setCacheHealth,
  updateCache,
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
export const selectLastUpdate = (state: { cache: CacheState }) => state.cache.lastUpdate;
export const selectCacheState = (state: { cache: CacheState }) => state.cache;

/**
 * Select overall cache hit rate percentage
 */
export const selectOverallHitRate = (state: { cache: CacheState }) =>
  state.cache.stats?.overall.overall_hit_rate ?? 0;

/**
 * Select total cache size in MB
 */
export const selectTotalCacheSize = (state: { cache: CacheState }) =>
  state.cache.stats?.overall.total_size_mb ?? 0;

/**
 * Select total chunks cached
 */
export const selectTotalChunks = (state: { cache: CacheState }) =>
  state.cache.stats?.overall.total_chunks ?? 0;

/**
 * Select tracks cached count
 */
export const selectTracksCached = (state: { cache: CacheState }) =>
  state.cache.stats?.overall.tracks_cached ?? 0;

export default cacheSlice.reducer;
