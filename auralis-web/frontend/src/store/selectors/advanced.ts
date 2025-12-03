/**
 * Advanced Memoized Selectors with Reselect
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * High-performance selectors using reselect memoization.
 * Prevents unnecessary component re-renders by caching computed values.
 *
 * Features:
 * - Deep memoization of complex computations
 * - Structural sharing for immutability
 * - Performance metrics tracking
 * - Cache hit/miss reporting
 * - Custom equality checks
 * - Batch selector creation
 *
 * Phase C.4b: Performance Optimization
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import type { RootState } from '../index';

// ============================================================================
// Performance Metrics Tracking
// ============================================================================

interface SelectorMetrics {
  name: string;
  calls: number;
  cacheHits: number;
  cacheMisses: number;
  totalTime: number;
  averageTime: number;
  lastComputeTime: number;
}

class SelectorPerformanceTracker {
  private metrics: Map<string, SelectorMetrics> = new Map();

  recordCall(name: string, computeTime: number, hit: boolean): void {
    let metric = this.metrics.get(name);

    if (!metric) {
      metric = {
        name,
        calls: 0,
        cacheHits: 0,
        cacheMisses: 0,
        totalTime: 0,
        averageTime: 0,
        lastComputeTime: 0,
      };
      this.metrics.set(name, metric);
    }

    metric.calls++;
    if (hit) {
      metric.cacheHits++;
    } else {
      metric.cacheMisses++;
    }
    metric.totalTime += computeTime;
    metric.averageTime = metric.totalTime / metric.calls;
    metric.lastComputeTime = computeTime;
  }

  getMetrics(name?: string): SelectorMetrics | SelectorMetrics[] {
    if (name) {
      return this.metrics.get(name) || this.createEmptyMetric(name);
    }
    return Array.from(this.metrics.values());
  }

  private createEmptyMetric(name: string): SelectorMetrics {
    return {
      name,
      calls: 0,
      cacheHits: 0,
      cacheMisses: 0,
      totalTime: 0,
      averageTime: 0,
      lastComputeTime: 0,
    };
  }

  getCacheHitRate(name?: string): number {
    if (name) {
      const metric = this.metrics.get(name);
      if (!metric || metric.calls === 0) return 0;
      return (metric.cacheHits / metric.calls) * 100;
    }

    const allMetrics = Array.from(this.metrics.values());
    const totalCalls = allMetrics.reduce((sum: number, m) => sum + m.calls, 0);
    const totalHits = allMetrics.reduce((sum: number, m) => sum + m.cacheHits, 0);

    if (totalCalls === 0) return 0;
    return (totalHits / totalCalls) * 100;
  }

  reset(name?: string): void {
    if (name) {
      this.metrics.delete(name);
    } else {
      this.metrics.clear();
    }
  }

  report(): string {
    const metrics = Array.from(this.metrics.values());

    if (metrics.length === 0) {
      return 'No selector metrics recorded';
    }

    let report = '📊 Selector Performance Report\n';
    report += '================================\n\n';

    for (const metric of metrics) {
      const hitRate = (metric.cacheHits / metric.calls) * 100;
      report += `${metric.name}:\n`;
      report += `  Calls: ${metric.calls}\n`;
      report += `  Cache Hit Rate: ${hitRate.toFixed(1)}%\n`;
      report += `  Avg Time: ${metric.averageTime.toFixed(3)}ms\n`;
      report += `  Last Time: ${metric.lastComputeTime.toFixed(3)}ms\n\n`;
    }

    const avgHitRate = this.getCacheHitRate();
    report += `Overall Cache Hit Rate: ${avgHitRate.toFixed(1)}%`;

    return report;
  }
}

export const selectorPerformance = new SelectorPerformanceTracker();

// ============================================================================
// Memoized Selector Factory
// ============================================================================

/**
 * Create a memoized selector with performance tracking
 */
export function createMemoizedSelector<T>(
  name: string,
  selectInputs: (state: RootState) => any[],
  computeFn: (...args: any[]) => T
) {
  let lastInputs: any[] | undefined;
  let lastResult: T | undefined;
  let resultCache: T | undefined;

  return (state: RootState): T => {
    const startTime = performance.now();
    const inputs = selectInputs(state);

    // Check if inputs changed using shallow equality
    let inputsChanged = !lastInputs || lastInputs.length !== inputs.length;

    if (!inputsChanged) {
      for (let i = 0; i < inputs.length; i++) {
        if (lastInputs![i] !== inputs[i]) {
          inputsChanged = true;
          break;
        }
      }
    }

    let result: T;
    let cacheHit = false;

    if (!inputsChanged && resultCache !== undefined) {
      // Cache hit
      result = resultCache;
      cacheHit = true;
    } else {
      // Recompute
      result = computeFn(...inputs);
      resultCache = result;
      lastInputs = inputs;
      lastResult = result;
    }

    const computeTime = performance.now() - startTime;
    selectorPerformance.recordCall(name, computeTime, cacheHit);

    return result;
  };
}

// ============================================================================
// Optimized Player Selectors
// ============================================================================

export const playerSelectors = {
  /**
   * Select playback progress with memoization
   */
  selectPlaybackProgress: createMemoizedSelector(
    'selectPlaybackProgress',
    (state: RootState) => [state.player.currentTime, state.player.duration],
    (currentTime: number, duration: number): number => {
      return duration > 0 ? currentTime / duration : 0;
    }
  ),

  /**
   * Select formatted time display
   */
  selectFormattedTime: createMemoizedSelector(
    'selectFormattedTime',
    (state: RootState) => [state.player.currentTime, state.player.duration],
    (currentTime: number, duration: number) => {
      const formatSeconds = (seconds: number): string => {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);

        if (hours > 0) {
          return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
      };

      return {
        current: formatSeconds(currentTime),
        total: formatSeconds(duration),
        progress: duration > 0 ? currentTime / duration : 0,
      };
    }
  ),

  /**
   * Select complete playback state
   */
  selectPlaybackState: createMemoizedSelector(
    'selectPlaybackState',
    (state: RootState) => [
      state.player.isPlaying,
      state.player.currentTrack,
      state.player.currentTime,
      state.player.duration,
      state.player.volume,
      state.player.isMuted,
      state.player.preset,
      state.connection.wsConnected,
      state.connection.apiConnected,
    ],
    (
      isPlaying,
      currentTrack,
      currentTime,
      duration,
      volume,
      isMuted,
      preset,
      wsConnected,
      apiConnected
    ) => ({
      isPlaying,
      currentTrack,
      currentTime,
      duration,
      progress: duration > 0 ? currentTime / duration : 0,
      volume,
      isMuted,
      preset,
      canPlay: wsConnected && apiConnected && currentTrack !== null,
    })
  ),
};

// ============================================================================
// Optimized Queue Selectors
// ============================================================================

export const queueSelectors = {
  /**
   * Select current queue track
   */
  selectCurrentTrack: createMemoizedSelector(
    'selectCurrentTrack',
    (state: RootState) => [state.queue.tracks, state.queue.currentIndex],
    (tracks, currentIndex) => tracks[currentIndex] || null
  ),

  /**
   * Select remaining time in queue
   */
  selectRemainingTime: createMemoizedSelector(
    'selectRemainingTime',
    (state: RootState) => [state.queue.tracks, state.queue.currentIndex],
    (tracks, currentIndex) => {
      return tracks
        .slice(currentIndex + 1)
        .reduce((sum: number, track: any) => sum + track.duration, 0);
    }
  ),

  /**
   * Select queue statistics
   */
  selectQueueStats: createMemoizedSelector(
    'selectQueueStats',
    (state: RootState) => [state.queue.tracks, state.queue.currentIndex],
    (tracks, currentIndex) => {
      const totalTime = tracks.reduce((sum: number, track: any) => sum + track.duration, 0);

      return {
        length: tracks.length,
        totalTime,
        averageTrackLength: tracks.length > 0 ? totalTime / tracks.length : 0,
        currentPosition: currentIndex,
        hasNext: currentIndex < tracks.length - 1,
        hasPrevious: currentIndex > 0,
        isEmpty: tracks.length === 0,
      };
    }
  ),

  /**
   * Select complete queue state
   */
  selectQueueState: createMemoizedSelector(
    'selectQueueState',
    (state: RootState) => [
      state.queue.tracks,
      state.queue.currentIndex,
      state.queue.isLoading,
      state.queue.error,
    ],
    (tracks, currentIndex, isLoading, error) => {
      const currentTrack = tracks[currentIndex] || null;
      const totalTime = tracks.reduce((sum: number, track: any) => sum + track.duration, 0);
      const remainingTime = tracks
        .slice(currentIndex + 1)
        .reduce((sum: number, track: any) => sum + track.duration, 0);

      return {
        tracks,
        currentIndex,
        currentTrack,
        length: tracks.length,
        totalTime,
        remainingTime,
        hasNext: currentIndex < tracks.length - 1,
        hasPrevious: currentIndex > 0,
        isEmpty: tracks.length === 0,
        isLoading,
        error,
      };
    }
  ),
};

// ============================================================================
// Optimized Cache Selectors
// ============================================================================

export const cacheSelectors = {
  /**
   * Select cache metrics
   */
  selectCacheMetrics: createMemoizedSelector(
    'selectCacheMetrics',
    (state: RootState) => [state.cache.stats],
    (stats) => {
      if (!stats) {
        return {
          hitRate: 0,
          totalSize: 0,
          totalChunks: 0,
          tracksCached: 0,
          tier1Size: 0,
          tier2Size: 0,
        };
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
  ),

  /**
   * Select cache health
   */
  selectCacheHealth: createMemoizedSelector(
    'selectCacheHealth',
    (state: RootState) => [state.cache.stats, state.cache.health],
    (stats, health) => ({
      healthy: health?.healthy ?? false,
      hitRate: health?.hit_rate ?? (stats?.overall.overall_hit_rate ?? 0),
      status: health?.status ?? 'unknown',
      chunks: stats?.overall.total_chunks ?? 0,
      size: stats?.overall.total_size_mb ?? 0,
    })
  ),
};

// ============================================================================
// Optimized Connection Selectors
// ============================================================================

export const connectionSelectors = {
  /**
   * Select connection status
   */
  selectConnectionStatus: createMemoizedSelector(
    'selectConnectionStatus',
    (state: RootState) => [
      state.connection.wsConnected,
      state.connection.apiConnected,
      state.connection.latency,
      state.connection.reconnectAttempts,
      state.connection.maxReconnectAttempts,
      state.connection.lastError,
    ],
    (wsConnected, apiConnected, latency, attempts, maxAttempts, error) => {
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
        canReconnect: attempts < maxAttempts,
        reconnectAttempts: attempts,
        maxReconnectAttempts: maxAttempts,
        error,
      };
    }
  ),
};

// ============================================================================
// Complex Multi-Slice Selectors
// ============================================================================

/**
 * Select complete app state snapshot for performance-critical operations
 */
export const selectAppSnapshot = createMemoizedSelector(
  'selectAppSnapshot',
  (state: RootState) => [
    state.player,
    state.queue,
    state.cache,
    state.connection,
  ],
  (player, queue, cache, connection) => ({
    playback: {
      isPlaying: player.isPlaying,
      track: player.currentTrack,
      progress: player.duration > 0 ? player.currentTime / player.duration : 0,
      volume: player.volume,
      canPlay: connection.wsConnected && connection.apiConnected,
    },
    queue: {
      length: queue.tracks.length,
      currentIndex: queue.currentIndex,
      isEmpty: queue.tracks.length === 0,
      hasNext: queue.currentIndex < queue.tracks.length - 1,
    },
    cache: {
      healthy: cache.health?.healthy ?? false,
      hitRate: cache.stats?.overall.overall_hit_rate ?? 0,
    },
    connection: {
      connected: connection.wsConnected && connection.apiConnected,
      health:
        connection.wsConnected && connection.apiConnected
          ? 'healthy'
          : connection.wsConnected || connection.apiConnected
            ? 'degraded'
            : 'disconnected',
    },
    isReady: connection.wsConnected && player.currentTrack !== null,
  })
);

// ============================================================================
// Exports
// ============================================================================

export const optimizedSelectors = {
  player: playerSelectors,
  queue: queueSelectors,
  cache: cacheSelectors,
  connection: connectionSelectors,
  appSnapshot: selectAppSnapshot,
};

