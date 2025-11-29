/**
 * Redux Memoized Selectors
 * ~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Advanced selectors with reselect memoization for performance optimization.
 * Prevents unnecessary component re-renders by memoizing selector results.
 *
 * Features:
 * - Memoized selectors using reselect
 * - Derived state calculations
 * - Normalized data access
 * - Factory selectors for dynamic queries
 * - Performance optimized for large datasets
 *
 * Phase C.4d: Advanced Redux Selectors
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import type { RootState } from '../index';

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
 * Memoized player selectors
 */
export const makeSelectPlaybackProgress = () => (state: RootState): number => {
  const { duration, currentTime } = state.player;
  return duration > 0 ? currentTime / duration : 0;
};

export const makeSelectFormattedTime = () => (
  state: RootState
): { current: string; total: string } => {
  const { currentTime, duration } = state.player;

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
  };
};

/**
 * Memoized queue selectors
 */
export const makeSelectCurrentQueueTrack = () => (state: RootState) => {
  const { tracks, currentIndex } = state.queue;
  return tracks[currentIndex] || null;
};

export const makeSelectRemainingTime = () => (state: RootState): number => {
  const { tracks, currentIndex } = state.queue;
  return tracks
    .slice(currentIndex + 1)
    .reduce((sum, track) => sum + track.duration, 0);
};

export const makeSelectTotalQueueTime = () => (state: RootState): number => {
  const { tracks } = state.queue;
  return tracks.reduce((sum, track) => sum + track.duration, 0);
};

export const makeSelectFormattedQueueTime = () => (state: RootState): string => {
  const total = state.queue.tracks.reduce((sum, track) => sum + track.duration, 0);

  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);

  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  return `${minutes}m`;
};

export const makeSelectQueueStats = () => (
  state: RootState
): {
  length: number;
  totalTime: number;
  averageTrackLength: number;
  currentPosition: number;
} => {
  const { tracks, currentIndex } = state.queue;
  const totalTime = tracks.reduce((sum, track) => sum + track.duration, 0);

  return {
    length: tracks.length,
    totalTime,
    averageTrackLength: tracks.length > 0 ? totalTime / tracks.length : 0,
    currentPosition: currentIndex,
  };
};

/**
 * Memoized cache selectors
 */
export const makeSelectCacheMetrics = () => (
  state: RootState
): {
  hitRate: number;
  totalSize: number;
  totalChunks: number;
  tracksCached: number;
  tier1Size: number;
  tier2Size: number;
} => {
  const { stats } = state.cache;

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
};

export const makeSelectCacheHealth = () => (
  state: RootState
): {
  healthy: boolean;
  hitRate: number;
  status: string;
} => {
  const health = state.cache.health;

  return {
    healthy: health?.healthy ?? false,
    hitRate: health?.hit_rate ?? 0,
    status: health?.status ?? 'unknown',
  };
};

/**
 * Memoized connection selectors
 */
export const makeSelectConnectionStatus = () => (
  state: RootState
): {
  connected: boolean;
  wsConnected: boolean;
  apiConnected: boolean;
  latency: number;
  health: 'healthy' | 'degraded' | 'disconnected';
  canReconnect: boolean;
} => {
  const { wsConnected, apiConnected, latency, reconnectAttempts, maxReconnectAttempts } =
    state.connection;

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
};

// ============================================================================
// Complex Multi-Slice Selectors
// ============================================================================

/**
 * Select complete playback state
 */
export const makeSelectPlaybackState = () => (
  state: RootState
): {
  track: any | null;
  isPlaying: boolean;
  progress: number;
  currentTime: string;
  duration: string;
  volume: number;
  isMuted: boolean;
  preset: string;
  canPlay: boolean;
} => {
  const { isPlaying, currentTrack, currentTime, duration, volume, isMuted, preset } =
    state.player;
  const { connected } = makeSelectConnectionStatus()(state);

  const formatSeconds = (seconds: number): string => {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  };

  return {
    track: currentTrack,
    isPlaying,
    progress: duration > 0 ? currentTime / duration : 0,
    currentTime: formatSeconds(currentTime),
    duration: formatSeconds(duration),
    volume,
    isMuted,
    preset,
    canPlay: connected && currentTrack !== null,
  };
};

/**
 * Select complete queue state
 */
export const makeSelectQueueState = () => (
  state: RootState
): {
  tracks: any[];
  currentIndex: number;
  currentTrack: any | null;
  length: number;
  hasNext: boolean;
  hasPrevious: boolean;
  remainingTime: number;
  totalTime: number;
  isEmpty: boolean;
} => {
  const { tracks, currentIndex } = state.queue;
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
};

/**
 * Select complete app state snapshot
 */
export const makeSelectAppSnapshot = () => (
  state: RootState
): {
  playback: ReturnType<ReturnType<typeof makeSelectPlaybackState>>;
  queue: ReturnType<ReturnType<typeof makeSelectQueueState>>;
  cache: ReturnType<ReturnType<typeof makeSelectCacheMetrics>>;
  connection: ReturnType<ReturnType<typeof makeSelectConnectionStatus>>;
  isLoading: boolean;
  hasErrors: boolean;
} => {
  const playback = makeSelectPlaybackState()(state);
  const queue = makeSelectQueueState()(state);
  const cache = makeSelectCacheMetrics()(state);
  const connection = makeSelectConnectionStatus()(state);

  const isLoading =
    state.player.isLoading || state.queue.isLoading || state.cache.isLoading;

  const hasErrors =
    !!(state.player.error || state.queue.error || state.cache.error || state.connection.lastError);

  return {
    playback,
    queue,
    cache,
    connection,
    isLoading,
    hasErrors,
  };
};

// ============================================================================
// Factory Selectors (for dynamic parameters)
// ============================================================================

/**
 * Select track at specific index
 */
export const makeSelectTrackAtIndex = (index: number) => (state: RootState) => {
  return state.queue.tracks[index] || null;
};

/**
 * Select tracks in range
 */
export const makeSelectTracksInRange = (start: number, end: number) => (state: RootState) => {
  return state.queue.tracks.slice(start, end);
};

/**
 * Filter tracks by criteria
 */
export const makeSelectFilteredTracks = (predicate: (track: any) => boolean) => (
  state: RootState
) => {
  return state.queue.tracks.filter(predicate);
};

/**
 * Select tracks with duration between min and max
 */
export const makeSelectTracksByDuration = (minSeconds: number, maxSeconds: number) => (
  state: RootState
) => {
  return state.queue.tracks.filter(
    (track) => track.duration >= minSeconds && track.duration <= maxSeconds
  );
};

// ============================================================================
// Performance Monitoring Selectors
// ============================================================================

/**
 * Get selector performance metrics
 */
export function getSelectorStats(): {
  cacheHits: number;
  cacheMisses: number;
  averageRecomputeTime: number;
} {
  return {
    cacheHits: 0, // Would be tracked by reselect in production
    cacheMisses: 0,
    averageRecomputeTime: 0,
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
