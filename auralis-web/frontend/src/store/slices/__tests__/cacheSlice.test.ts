/**
 * cacheSlice reducer unit tests (#2815)
 *
 * Covers all action creators, cache clearing, and derived selectors.
 */

import reducer, {
  setCacheStats,
  setCacheHealth,
  updateCache,
  setIsLoading,
  setError,
  clearError,
  clearCacheLocal,
  resetCache,
  selectCacheStats,
  selectCacheHealth,
  selectIsHealthy,
  selectIsLoading,
  selectError,
  selectOverallHitRate,
  selectTotalCacheSize,
  selectTotalChunks,
  selectTracksCached,
} from '../cacheSlice';
import type { CacheState } from '../cacheSlice';
import type { CacheStats, CacheHealth } from '@/services/api/standardizedAPIClient';

const initialState: CacheState = {
  stats: null,
  health: null,
  isLoading: false,
  error: null,
  lastUpdate: 0,
};

const mockStats: CacheStats = {
  tier1: { chunks: 10, size_mb: 50, hits: 80, misses: 20, hit_rate: 0.8 },
  tier2: { chunks: 5, size_mb: 100, hits: 40, misses: 10, hit_rate: 0.8 },
  overall: {
    total_chunks: 15,
    total_size_mb: 150,
    total_hits: 120,
    total_misses: 30,
    overall_hit_rate: 0.8,
    tracks_cached: 7,
  },
  tracks: {},
};

const mockHealth: CacheHealth = {
  healthy: true,
  tier1_size_mb: 50,
  tier1_healthy: true,
  tier2_size_mb: 100,
  tier2_healthy: true,
  total_size_mb: 150,
  memory_healthy: true,
  tier1_hit_rate: 0.8,
  overall_hit_rate: 0.8,
  timestamp: '2026-03-20T00:00:00Z',
};

describe('cacheSlice', () => {
  it('should return initial state', () => {
    const state = reducer(undefined, { type: 'unknown' });
    expect(state.stats).toBeNull();
    expect(state.health).toBeNull();
    expect(state.isLoading).toBe(false);
    expect(state.error).toBeNull();
  });

  // ─── Stats/Health setters ─────────────────────────────────────

  it('setCacheStats sets stats and timestamp', () => {
    const state = reducer(initialState, setCacheStats(mockStats));
    expect(state.stats).toEqual(mockStats);
    expect(state.lastUpdate).toBeGreaterThan(0);
  });

  it('setCacheHealth sets health and timestamp', () => {
    const state = reducer(initialState, setCacheHealth(mockHealth));
    expect(state.health).toEqual(mockHealth);
    expect(state.lastUpdate).toBeGreaterThan(0);
  });

  it('updateCache sets both stats and health', () => {
    const state = reducer(initialState, updateCache({ stats: mockStats, health: mockHealth }));
    expect(state.stats).toEqual(mockStats);
    expect(state.health).toEqual(mockHealth);
  });

  it('updateCache with only stats preserves null health', () => {
    const state = reducer(initialState, updateCache({ stats: mockStats }));
    expect(state.stats).toEqual(mockStats);
    expect(state.health).toBeNull();
  });

  // ─── Loading/Error ────────────────────────────────────────────

  it('setIsLoading sets loading state', () => {
    const state = reducer(initialState, setIsLoading(true));
    expect(state.isLoading).toBe(true);
  });

  it('setError sets error message', () => {
    const state = reducer(initialState, setError('cache error'));
    expect(state.error).toBe('cache error');
  });

  it('clearError clears error', () => {
    let state = reducer(initialState, setError('err'));
    state = reducer(state, clearError());
    expect(state.error).toBeNull();
  });

  // ─── Clear/Reset ──────────────────────────────────────────────

  it('clearCacheLocal zeros out stats structure', () => {
    let state = reducer(initialState, setCacheStats(mockStats));
    state = reducer(state, clearCacheLocal());
    expect(state.stats).not.toBeNull();
    expect(state.stats!.overall.total_chunks).toBe(0);
    expect(state.stats!.overall.total_size_mb).toBe(0);
    expect(state.stats!.overall.tracks_cached).toBe(0);
    expect(state.stats!.tier1.chunks).toBe(0);
    expect(state.stats!.tier2.chunks).toBe(0);
  });

  it('resetCache returns to initial state', () => {
    let state = reducer(initialState, setCacheStats(mockStats));
    state = reducer(state, setCacheHealth(mockHealth));
    state = reducer(state, setError('err'));
    state = reducer(state, resetCache());
    expect(state.stats).toBeNull();
    expect(state.health).toBeNull();
    expect(state.error).toBeNull();
  });

  // ─── Selectors ────────────────────────────────────────────────

  it('basic selectors return correct values', () => {
    const state: CacheState = {
      stats: mockStats,
      health: mockHealth,
      isLoading: true,
      error: 'err',
      lastUpdate: 1000,
    };
    const root = { cache: state };

    expect(selectCacheStats(root)).toEqual(mockStats);
    expect(selectCacheHealth(root)).toEqual(mockHealth);
    expect(selectIsLoading(root)).toBe(true);
    expect(selectError(root)).toBe('err');
  });

  it('selectIsHealthy derives from health.healthy', () => {
    expect(selectIsHealthy({ cache: { ...initialState, health: mockHealth } })).toBe(true);
    expect(selectIsHealthy({ cache: { ...initialState, health: { ...mockHealth, healthy: false } } })).toBe(false);
    expect(selectIsHealthy({ cache: initialState })).toBe(false); // null health
  });

  it('derived selectors return correct values with stats', () => {
    const root = { cache: { ...initialState, stats: mockStats } };
    expect(selectOverallHitRate(root)).toBe(0.8);
    expect(selectTotalCacheSize(root)).toBe(150);
    expect(selectTotalChunks(root)).toBe(15);
    expect(selectTracksCached(root)).toBe(7);
  });

  it('derived selectors return 0 when stats is null', () => {
    const root = { cache: initialState };
    expect(selectOverallHitRate(root)).toBe(0);
    expect(selectTotalCacheSize(root)).toBe(0);
    expect(selectTotalChunks(root)).toBe(0);
    expect(selectTracksCached(root)).toBe(0);
  });
});
