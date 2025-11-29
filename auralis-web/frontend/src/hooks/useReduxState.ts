/**
 * Redux State Hooks
 * ~~~~~~~~~~~~~~~~
 *
 * Convenience hooks for accessing Redux state and dispatching actions.
 * Provides a cleaner API for components instead of raw useSelector/useDispatch.
 *
 * Features:
 * - Memoized selectors to prevent unnecessary re-renders
 * - Type-safe actions
 * - Batch updates for related state
 * - Loading and error state helpers
 *
 * Phase C.4a: Redux Integration
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { useSelector, useDispatch } from 'react-redux';
import { useCallback } from 'react';
import type { RootState, AppDispatch } from '@/store';
import * as playerActions from '@/store/slices/playerSlice';
import * as queueActions from '@/store/slices/queueSlice';
import * as cacheActions from '@/store/slices/cacheSlice';
import * as connectionActions from '@/store/slices/connectionSlice';

// ============================================================================
// Player State Hooks
// ============================================================================

/**
 * Access entire player state
 */
export const usePlayerState = () => {
  return useSelector((state: RootState) => state.player);
};

/**
 * Access player playback controls and state
 */
export const usePlayer = () => {
  const dispatch = useDispatch<AppDispatch>();
  const state = useSelector((state: RootState) => state.player);

  return {
    // State
    isPlaying: state.isPlaying,
    currentTrack: state.currentTrack,
    currentTime: state.currentTime,
    duration: state.duration,
    volume: state.volume,
    isMuted: state.isMuted,
    preset: state.preset,
    isLoading: state.isLoading,
    error: state.error,

    // Actions
    play: useCallback(() => dispatch(playerActions.setIsPlaying(true)), [dispatch]),
    pause: useCallback(() => dispatch(playerActions.setIsPlaying(false)), [dispatch]),
    togglePlay: useCallback(
      () => dispatch(playerActions.setIsPlaying(!state.isPlaying)),
      [dispatch, state.isPlaying]
    ),
    seek: useCallback(
      (time: number) => dispatch(playerActions.setCurrentTime(time)),
      [dispatch]
    ),
    setVolume: useCallback(
      (volume: number) => dispatch(playerActions.setVolume(volume)),
      [dispatch]
    ),
    setMuted: useCallback(
      (muted: boolean) => dispatch(playerActions.setMuted(muted)),
      [dispatch]
    ),
    toggleMute: useCallback(
      () => dispatch(playerActions.toggleMute()),
      [dispatch]
    ),
    setPreset: useCallback(
      (preset: playerActions.PresetName) => dispatch(playerActions.setPreset(preset)),
      [dispatch]
    ),
    setTrack: useCallback(
      (track: any | null) => dispatch(playerActions.setCurrentTrack(track)),
      [dispatch]
    ),
  };
};

// ============================================================================
// Queue State Hooks
// ============================================================================

/**
 * Access entire queue state
 */
export const useQueueState = () => {
  return useSelector((state: RootState) => state.queue);
};

/**
 * Access queue management controls
 */
export const useQueue = () => {
  const dispatch = useDispatch<AppDispatch>();
  const state = useSelector((state: RootState) => state.queue);

  return {
    // State
    tracks: state.tracks,
    currentIndex: state.currentIndex,
    currentTrack: state.tracks[state.currentIndex] || null,
    queueLength: state.tracks.length,
    isLoading: state.isLoading,
    error: state.error,

    // Computed state
    remainingTime: state.tracks
      .slice(state.currentIndex + 1)
      .reduce((sum, track) => sum + track.duration, 0),
    totalTime: state.tracks.reduce((sum, track) => sum + track.duration, 0),

    // Actions
    add: useCallback(
      (track: any) => dispatch(queueActions.addTrack(track)),
      [dispatch]
    ),
    addMany: useCallback(
      (tracks: any[]) => dispatch(queueActions.addTracks(tracks)),
      [dispatch]
    ),
    remove: useCallback(
      (index: number) => dispatch(queueActions.removeTrack(index)),
      [dispatch]
    ),
    reorder: useCallback(
      (fromIndex: number, toIndex: number) =>
        dispatch(queueActions.reorderTrack({ fromIndex, toIndex })),
      [dispatch]
    ),
    setCurrentIndex: useCallback(
      (index: number) => dispatch(queueActions.setCurrentIndex(index)),
      [dispatch]
    ),
    next: useCallback(() => dispatch(queueActions.nextTrack()), [dispatch]),
    previous: useCallback(() => dispatch(queueActions.previousTrack()), [dispatch]),
    clear: useCallback(() => dispatch(queueActions.clearQueue()), [dispatch]),
    setQueue: useCallback(
      (tracks: any[]) => dispatch(queueActions.setQueue(tracks)),
      [dispatch]
    ),
  };
};

// ============================================================================
// Cache State Hooks
// ============================================================================

/**
 * Access entire cache state
 */
export const useCacheState = () => {
  return useSelector((state: RootState) => state.cache);
};

/**
 * Access cache monitoring and management
 */
export const useCache = () => {
  const dispatch = useDispatch<AppDispatch>();
  const state = useSelector((state: RootState) => state.cache);

  return {
    // State
    stats: state.stats,
    health: state.health,
    isLoading: state.isLoading,
    error: state.error,
    lastUpdate: state.lastUpdate,

    // Computed health
    isHealthy: state.health?.healthy ?? false,
    hitRate: state.stats?.overall.overall_hit_rate ?? 0,
    totalSize: state.stats?.overall.total_size_mb ?? 0,
    totalChunks: state.stats?.overall.total_chunks ?? 0,
    tracksCached: state.stats?.overall.tracks_cached ?? 0,

    // Actions
    setStats: useCallback(
      (stats: any) => dispatch(cacheActions.setCacheStats(stats)),
      [dispatch]
    ),
    setHealth: useCallback(
      (health: any) => dispatch(cacheActions.setCacheHealth(health)),
      [dispatch]
    ),
    clear: useCallback(
      () => dispatch(cacheActions.clearCacheLocal()),
      [dispatch]
    ),
    clearError: useCallback(
      () => dispatch(cacheActions.clearError()),
      [dispatch]
    ),
  };
};

// ============================================================================
// Connection State Hooks
// ============================================================================

/**
 * Access entire connection state
 */
export const useConnectionState = () => {
  return useSelector((state: RootState) => state.connection);
};

/**
 * Access connection status and management
 */
export const useConnection = () => {
  const dispatch = useDispatch<AppDispatch>();
  const state = useSelector((state: RootState) => state.connection);

  return {
    // State
    wsConnected: state.wsConnected,
    apiConnected: state.apiConnected,
    latency: state.latency,
    reconnectAttempts: state.reconnectAttempts,
    maxReconnectAttempts: state.maxReconnectAttempts,
    lastError: state.lastError,

    // Computed state
    isFullyConnected: state.wsConnected && state.apiConnected,
    canReconnect: state.reconnectAttempts < state.maxReconnectAttempts,
    connectionHealth:
      state.wsConnected && state.apiConnected
        ? 'healthy'
        : state.wsConnected || state.apiConnected
          ? 'degraded'
          : 'disconnected',

    // Actions
    setWSConnected: useCallback(
      (connected: boolean) => dispatch(connectionActions.setWSConnected(connected)),
      [dispatch]
    ),
    setAPIConnected: useCallback(
      (connected: boolean) => dispatch(connectionActions.setAPIConnected(connected)),
      [dispatch]
    ),
    setLatency: useCallback(
      (latency: number) => dispatch(connectionActions.setLatency(latency)),
      [dispatch]
    ),
    incrementReconnectAttempts: useCallback(
      () => dispatch(connectionActions.incrementReconnectAttempts()),
      [dispatch]
    ),
    resetReconnectAttempts: useCallback(
      () => dispatch(connectionActions.resetReconnectAttempts()),
      [dispatch]
    ),
    clearError: useCallback(
      () => dispatch(connectionActions.clearError()),
      [dispatch]
    ),
  };
};

// ============================================================================
// Combined State Hook
// ============================================================================

/**
 * Access complete application state in one hook
 * Useful for complex components needing multiple slices
 */
export const useAppState = () => {
  const player = usePlayerState();
  const queue = useQueueState();
  const cache = useCacheState();
  const connection = useConnectionState();

  return {
    player,
    queue,
    cache,
    connection,
  };
};

// ============================================================================
// Convenience Hooks
// ============================================================================

/**
 * Check if any loading is in progress
 */
export const useIsLoading = () => {
  const player = useSelector((state: RootState) => state.player.isLoading);
  const queue = useSelector((state: RootState) => state.queue.isLoading);
  const cache = useSelector((state: RootState) => state.cache.isLoading);

  return player || queue || cache;
};

/**
 * Check if any errors exist
 */
export const useAppErrors = () => {
  const playerError = useSelector((state: RootState) => state.player.error);
  const queueError = useSelector((state: RootState) => state.queue.error);
  const cacheError = useSelector((state: RootState) => state.cache.error);
  const connectionError = useSelector((state: RootState) => state.connection.lastError);

  return {
    playerError,
    queueError,
    cacheError,
    connectionError,
    hasErrors: !!(playerError || queueError || cacheError || connectionError),
  };
};

/**
 * Check connection status with health information
 */
export const useConnectionHealth = () => {
  const connection = useConnectionState();

  return {
    connected: connection.wsConnected && connection.apiConnected,
    wsConnected: connection.wsConnected,
    apiConnected: connection.apiConnected,
    latency: connection.latency,
    attempting: connection.reconnectAttempts > 0 && connection.reconnectAttempts < connection.maxReconnectAttempts,
    failed: connection.reconnectAttempts >= connection.maxReconnectAttempts,
    health:
      connection.wsConnected && connection.apiConnected
        ? 'connected'
        : connection.wsConnected || connection.apiConnected
          ? 'partial'
          : 'disconnected',
  };
};

/**
 * Get current playback progress (0-1)
 */
export const usePlaybackProgress = () => {
  const { currentTime, duration } = usePlayerState();
  return duration > 0 ? currentTime / duration : 0;
};

/**
 * Format remaining time in queue
 */
export const useQueueTimeRemaining = () => {
  const queue = useQueueState();
  const remaining = queue.tracks
    .slice(queue.currentIndex + 1)
    .reduce((sum, track) => sum + track.duration, 0);

  const hours = Math.floor(remaining / 3600);
  const minutes = Math.floor((remaining % 3600) / 60);
  const seconds = remaining % 60;

  return {
    total: remaining,
    formatted: hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m ${seconds}s`,
  };
};
