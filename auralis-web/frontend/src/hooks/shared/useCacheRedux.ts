/**
 * Cache Redux Hooks
 * ~~~~~~~~~~~~~~~~~
 *
 * Cache-slice state and action hooks. Split out of useReduxState.ts (#5239),
 * which re-exports everything here.
 *
 * @copyright (C) 2024 Auralis Team
 * @license AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
 */

import { useSelector, useDispatch, shallowEqual } from 'react-redux';
import { useCallback, useMemo } from 'react';
import type { RootState, AppDispatch } from '@/store';
import * as cacheActions from '@/store/slices/cacheSlice';
import type { CacheStats, CacheHealth } from '@/services/api/standardizedAPIClient';

/**
 * Access entire cache state
 */
export const useCacheState = () => {
  return useSelector((state: RootState) => state.cache, shallowEqual);
};

/**
 * Access cache monitoring and management
 */
export const useCache = () => {
  const dispatch = useDispatch<AppDispatch>();
  const state = useSelector((state: RootState) => state.cache, shallowEqual);

  const setStats = useCallback(
    (stats: CacheStats) => dispatch(cacheActions.setCacheStats(stats)),
    [dispatch]
  );
  const setHealth = useCallback(
    (health: CacheHealth) => dispatch(cacheActions.setCacheHealth(health)),
    [dispatch]
  );
  const clear = useCallback(
    () => dispatch(cacheActions.clearCacheLocal()),
    [dispatch]
  );
  const clearError = useCallback(
    () => dispatch(cacheActions.clearError()),
    [dispatch]
  );

  // #3619: stable object identity (matches usePlayer pattern).
  return useMemo(
    () => ({
      stats: state.stats,
      health: state.health,
      isLoading: state.isLoading,
      error: state.error,
      lastUpdated: state.lastUpdated,
      isHealthy: state.health?.healthy ?? false,
      hitRate: state.stats?.overall.overall_hit_rate ?? 0,
      totalSize: state.stats?.overall.total_size_mb ?? 0,
      totalChunks: state.stats?.overall.total_chunks ?? 0,
      tracksCached: state.stats?.overall.tracks_cached ?? 0,
      setStats,
      setHealth,
      clear,
      clearError,
    }),
    [state.stats, state.health, state.isLoading, state.error, state.lastUpdated, setStats, setHealth, clear, clearError]
  );
};
