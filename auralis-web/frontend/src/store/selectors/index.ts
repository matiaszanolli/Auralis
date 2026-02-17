/**
 * Redux Memoized Selectors
 * ~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Memoized selectors using createSelector from @reduxjs/toolkit (Reselect).
 * Prevents unnecessary component re-renders by returning the same reference
 * when inputs haven't changed.
 *
 * Phase C.4d: Advanced Redux Selectors
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { createSelector } from '@reduxjs/toolkit';
import type { RootState } from '../index';

// ============================================================================
// Helper
// ============================================================================

const formatSeconds = (seconds: number): string => {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
};

// ============================================================================
// Simple Selector Utilities
// ============================================================================

/**
 * Basic selectors (non-memoized, for simple properties)
 */
export const playerSelectors = {
  selectIsPlaying: (state: RootState) => state.player.isPlaying,
  selectCurrentTrack: (state: RootState) => state.player.currentTrack,
  selectCurrentTime: (state: RootState) => state.player.currentTime,
  selectDuration: (state: RootState) => state.player.duration,
  selectVolume: (state: RootState) => state.player.volume,
  selectIsMuted: (state: RootState) => state.player.isMuted,
  selectPreset: (state: RootState) => state.player.preset,
  selectPlayerLoading: (state: RootState) => state.player.isLoading,
  selectPlayerError: (state: RootState) => state.player.error,
};

export const queueSelectors = {
  selectQueueTracks: (state: RootState) => state.queue.tracks,
  selectCurrentIndex: (state: RootState) => state.queue.currentIndex,
  selectQueueLoading: (state: RootState) => state.queue.isLoading,
  selectQueueError: (state: RootState) => state.queue.error,
};

export const cacheSelectors = {
  selectCacheStats: (state: RootState) => state.cache.stats,
  selectCacheHealth: (state: RootState) => state.cache.health,
  selectCacheLoading: (state: RootState) => state.cache.isLoading,
  selectCacheError: (state: RootState) => state.cache.error,
};

export const connectionSelectors = {
  selectWSConnected: (state: RootState) => state.connection.wsConnected,
  selectAPIConnected: (state: RootState) => state.connection.apiConnected,
  selectLatency: (state: RootState) => state.connection.latency,
  selectReconnectAttempts: (state: RootState) => state.connection.reconnectAttempts,
  selectConnectionError: (state: RootState) => state.connection.lastError,
};

// ============================================================================
// Memoized Derived Selectors
// ============================================================================

/**
 * Player selectors
 */
export const selectPlaybackProgress = createSelector(
  [(state: RootState) => state.player.currentTime, (state: RootState) => state.player.duration],
  (currentTime, duration): number => (duration > 0 ? currentTime / duration : 0)
);

export const selectFormattedTime = createSelector(
  [(state: RootState) => state.player.currentTime, (state: RootState) => state.player.duration],
  (currentTime, duration) => ({
    current: formatSeconds(currentTime),
    total: formatSeconds(duration),
  })
);

/**
 * Queue selectors
 */
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
  [(state: RootState) => state.queue.tracks],
  (tracks): string => {
    const total = tracks.reduce((sum, track) => sum + track.duration, 0);
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
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
 * Cache selectors
 */
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

/**
 * Connection selectors
 */
export const selectConnectionStatus = createSelector(
  [
    (state: RootState) => state.connection.wsConnected,
    (state: RootState) => state.connection.apiConnected,
    (state: RootState) => state.connection.latency,
    (state: RootState) => state.connection.reconnectAttempts,
    (state: RootState) => state.connection.maxReconnectAttempts,
  ],
  (wsConnected, apiConnected, latency, reconnectAttempts, maxReconnectAttempts) => {
    let health: 'healthy' | 'degraded' | 'disconnected' = 'disconnected';
    if (wsConnected && apiConnected) {
      health = 'healthy';
    } else if (wsConnected || apiConnected) {
      health = 'degraded';
    }
    return {
      connected: wsConnected && apiConnected,
      wsConnected,
      apiConnected,
      latency,
      health,
      canReconnect: reconnectAttempts < maxReconnectAttempts,
    };
  }
);

// ============================================================================
// Complex Multi-Slice Selectors
// ============================================================================

/**
 * Complete playback state
 */
export const selectPlaybackState = createSelector(
  [
    (state: RootState) => state.player.isPlaying,
    (state: RootState) => state.player.currentTrack,
    (state: RootState) => state.player.currentTime,
    (state: RootState) => state.player.duration,
    (state: RootState) => state.player.volume,
    (state: RootState) => state.player.isMuted,
    (state: RootState) => state.player.preset,
    (state: RootState) => state.connection.wsConnected,
    (state: RootState) => state.connection.apiConnected,
  ],
  (isPlaying, currentTrack, currentTime, duration, volume, isMuted, preset, wsConnected, apiConnected) => ({
    track: currentTrack,
    isPlaying,
    progress: duration > 0 ? currentTime / duration : 0,
    currentTime: formatSeconds(currentTime),
    duration: formatSeconds(duration),
    volume,
    isMuted,
    preset,
    canPlay: wsConnected && apiConnected && currentTrack !== null,
  })
);

/**
 * Complete queue state
 */
export const selectQueueState = createSelector(
  [(state: RootState) => state.queue.tracks, (state: RootState) => state.queue.currentIndex],
  (tracks, currentIndex) => {
    const currentTrack = tracks[currentIndex] || null;
    const remainingTime = tracks
      .slice(currentIndex + 1)
      .reduce((sum, track) => sum + track.duration, 0);
    const totalTime = tracks.reduce((sum, track) => sum + track.duration, 0);

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

/**
 * Complete app state snapshot
 */
export const selectAppSnapshot = createSelector(
  [selectPlaybackState, selectQueueState, selectCacheMetrics, selectConnectionStatus],
  (playback, queue, cache, connection) => ({
    playback,
    queue,
    cache,
    connection,
    isLoading: false,
    hasErrors: false,
  })
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
export const makeSelectFilteredTracks = (predicate: (track: any) => boolean) =>
  createSelector([(state: RootState) => state.queue.tracks], (tracks) => tracks.filter(predicate));

/**
 * Select tracks by duration range.
 * Usage: const selector = useMemo(() => makeSelectTracksByDuration(min, max), [min, max]);
 */
export const makeSelectTracksByDuration = (minSeconds: number, maxSeconds: number) =>
  createSelector([(state: RootState) => state.queue.tracks], (tracks) =>
    tracks.filter((track) => track.duration >= minSeconds && track.duration <= maxSeconds)
  );

// ============================================================================
// Backwards-compatible factory aliases (deprecated — use direct selectors above)
// ============================================================================

/** @deprecated Use selectPlaybackProgress directly */
export const makeSelectPlaybackProgress = () => selectPlaybackProgress;
/** @deprecated Use selectFormattedTime directly */
export const makeSelectFormattedTime = () => selectFormattedTime;
/** @deprecated Use selectCurrentQueueTrack directly */
export const makeSelectCurrentQueueTrack = () => selectCurrentQueueTrack;
/** @deprecated Use selectRemainingTime directly */
export const makeSelectRemainingTime = () => selectRemainingTime;
/** @deprecated Use selectTotalQueueTime directly */
export const makeSelectTotalQueueTime = () => selectTotalQueueTime;
/** @deprecated Use selectFormattedQueueTime directly */
export const makeSelectFormattedQueueTime = () => selectFormattedQueueTime;
/** @deprecated Use selectQueueStats directly */
export const makeSelectQueueStats = () => selectQueueStats;
/** @deprecated Use selectCacheMetrics directly */
export const makeSelectCacheMetrics = () => selectCacheMetrics;
/** @deprecated Use selectCacheHealthDerived directly */
export const makeSelectCacheHealth = () => selectCacheHealthDerived;
/** @deprecated Use selectConnectionStatus directly */
export const makeSelectConnectionStatus = () => selectConnectionStatus;
/** @deprecated Use selectPlaybackState directly */
export const makeSelectPlaybackState = () => selectPlaybackState;
/** @deprecated Use selectQueueState directly */
export const makeSelectQueueState = () => selectQueueState;
/** @deprecated Use selectAppSnapshot directly */
export const makeSelectAppSnapshot = () => selectAppSnapshot;

// ============================================================================
// Performance Monitoring
// ============================================================================

export interface SelectorMetrics {
  name: string;
  calls: number;
  cacheHits: number;
  cacheMisses: number;
  totalTime: number;
  averageTime: number;
  lastComputeTime: number;
}

export class SelectorPerformanceTracker {
  private metrics: Map<string, SelectorMetrics> = new Map();

  recordCall(name: string, computeTime: number, hit: boolean): void {
    let metric = this.metrics.get(name);
    if (!metric) {
      metric = { name, calls: 0, cacheHits: 0, cacheMisses: 0, totalTime: 0, averageTime: 0, lastComputeTime: 0 };
      this.metrics.set(name, metric);
    }
    metric.calls++;
    if (hit) { metric.cacheHits++; } else { metric.cacheMisses++; }
    metric.totalTime += computeTime;
    metric.averageTime = metric.totalTime / metric.calls;
    metric.lastComputeTime = computeTime;
  }

  getMetrics(name?: string): SelectorMetrics | SelectorMetrics[] {
    if (name) return this.metrics.get(name) || { name, calls: 0, cacheHits: 0, cacheMisses: 0, totalTime: 0, averageTime: 0, lastComputeTime: 0 };
    return Array.from(this.metrics.values());
  }

  getCacheHitRate(name?: string): number {
    if (name) {
      const m = this.metrics.get(name);
      return (m && m.calls > 0) ? (m.cacheHits / m.calls) * 100 : 0;
    }
    const all = Array.from(this.metrics.values());
    const calls = all.reduce((s, m) => s + m.calls, 0);
    const hits = all.reduce((s, m) => s + m.cacheHits, 0);
    return calls > 0 ? (hits / calls) * 100 : 0;
  }

  reset(name?: string): void {
    if (name) { this.metrics.delete(name); } else { this.metrics.clear(); }
  }

  report(): string {
    const metrics = Array.from(this.metrics.values());
    if (metrics.length === 0) return 'No selector metrics recorded';
    let out = '📊 Selector Performance Report\n================================\n\n';
    for (const m of metrics) {
      const rate = m.calls > 0 ? ((m.cacheHits / m.calls) * 100).toFixed(1) : '0.0';
      out += `${m.name}:\n  Calls: ${m.calls}\n  Cache Hit Rate: ${rate}%\n  Avg Time: ${m.averageTime.toFixed(3)}ms\n\n`;
    }
    out += `Overall Cache Hit Rate: ${this.getCacheHitRate().toFixed(1)}%`;
    return out;
  }
}

export const selectorPerformance = new SelectorPerformanceTracker();

/**
 * Create a memoized selector with performance tracking.
 * Prefer using createSelector from @reduxjs/toolkit for new selectors.
 * This factory is retained for backwards compatibility with performance/index.ts.
 */
export function createMemoizedSelector<T>(
  name: string,
  selectInputs: (state: RootState) => any[],
  computeFn: (...args: any[]) => T
): (state: RootState) => T {
  let lastInputs: any[] | undefined;
  let resultCache: T | undefined;

  return (state: RootState): T => {
    const startTime = performance.now();
    const inputs = selectInputs(state);

    let inputsChanged = !lastInputs || lastInputs.length !== inputs.length;
    if (!inputsChanged) {
      for (let i = 0; i < inputs.length; i++) {
        if (lastInputs![i] !== inputs[i]) { inputsChanged = true; break; }
      }
    }

    let result: T;
    if (!inputsChanged && resultCache !== undefined) {
      result = resultCache;
      selectorPerformance.recordCall(name, performance.now() - startTime, true);
    } else {
      result = computeFn(...inputs);
      resultCache = result;
      lastInputs = inputs;
      selectorPerformance.recordCall(name, performance.now() - startTime, false);
    }
    return result;
  };
}

// ============================================================================
// Exports
// ============================================================================

export const selectors = {
  player: playerSelectors,
  queue: queueSelectors,
  cache: cacheSelectors,
  connection: connectionSelectors,
  playback: makeSelectPlaybackState,
  queueState: makeSelectQueueState,
  appSnapshot: makeSelectAppSnapshot,
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
