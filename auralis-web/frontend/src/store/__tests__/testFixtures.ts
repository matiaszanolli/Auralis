/**
 * Redux Testing Fixtures and Utilities
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Pre-configured Redux store states and utilities for testing.
 * Provides common test scenarios and fixtures for faster test development.
 *
 * Features:
 * - Pre-configured store states for different scenarios
 * - Factory functions for creating test data
 * - Store setup utilities
 * - Mock data generators
 * - State verification helpers
 *
 * Phase C.4d: Redux Testing Utilities
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { configureStore } from '@reduxjs/toolkit';
import playerReducer from '../slices/playerSlice';
import queueReducer from '../slices/queueSlice';
import cacheReducer from '../slices/cacheSlice';
import connectionReducer from '../slices/connectionSlice';
import type { RootState } from '../index';

// ============================================================================
// Test Data Generators
// ============================================================================

/**
 * Generate mock track
 */
export const createMockTrack = (overrides?: Partial<any>) => ({
  id: Math.floor(Math.random() * 10000),
  title: `Track ${Math.random()}`,
  artist: `Artist ${Math.random()}`,
  album: 'Album',
  duration: Math.floor(Math.random() * 300) + 60,
  artworkUrl: 'https://example.com/cover.jpg',
  ...overrides,
});

/**
 * Generate multiple mock tracks
 */
export const createMockTracks = (count: number = 5) => {
  return Array.from({ length: count }, (_, i) =>
    createMockTrack({
      id: i + 1,
      title: `Track ${i + 1}`,
    })
  );
};

/**
 * Generate mock cache stats
 */
export const createMockCacheStats = (overrides?: Partial<any>) => ({
  tier1: {
    chunks: 4,
    size_mb: 6,
    hits: 100,
    misses: 5,
    hit_rate: 0.95,
  },
  tier2: {
    chunks: 8,
    size_mb: 120,
    hits: 50,
    misses: 50,
    hit_rate: 0.5,
  },
  overall: {
    total_chunks: 12,
    total_size_mb: 225,
    total_hits: 150,
    total_misses: 55,
    overall_hit_rate: 0.73,
    tracks_cached: 42,
  },
  tracks: {},
  ...overrides,
});

/**
 * Generate mock cache health
 */
export const createMockCacheHealth = (overrides?: Partial<any>) => ({
  healthy: true,
  hit_rate: 0.95,
  status: 'healthy',
  warnings: 0,
  tier1_size_mb: 6,
  tier1_healthy: true,
  tier2_size_mb: 120,
  tier2_healthy: true,
  total_size_mb: 126,
  memory_healthy: true,
  tier1_hit_rate: 0.95,
  overall_hit_rate: 0.73,
  timestamp: new Date().toISOString(),
  ...overrides,
});

// ============================================================================
// Store Fixtures
// ============================================================================

/**
 * Default empty store state
 */
const defaultStreamingInfo = {
  state: 'idle' as const,
  trackId: null,
  intensity: 1.0,
  progress: 0,
  bufferedSamples: 0,
  totalChunks: 0,
  processedChunks: 0,
  error: null,
};

export const emptyStoreState: RootState = {
  player: {
    isPlaying: false,
    currentTrack: null,
    currentTime: 0,
    duration: 0,
    volume: 70,
    isMuted: false,
    preset: 'adaptive',
    isLoading: false,
    error: null,
    lastUpdated: 0,
    streaming: {
      normal: { ...defaultStreamingInfo },
      enhanced: { ...defaultStreamingInfo },
    },
  },
  queue: {
    tracks: [],
    currentIndex: 0,
    isLoading: false,
    error: null,
    lastUpdated: 0,
  },
  cache: {
    stats: null,
    health: null,
    isLoading: false,
    error: null,
    lastUpdate: 0,
  },
  connection: {
    wsConnected: false,
    apiConnected: false,
    latency: 0,
    reconnectAttempts: 0,
    maxReconnectAttempts: 5,
    lastError: null,
    lastReconnectTime: 0,
    lastUpdated: 0,
  },
};

/**
 * Connected state with single track
 */
export const connectedWithTrackState: RootState = {
  ...emptyStoreState,
  player: {
    ...emptyStoreState.player,
    currentTrack: createMockTrack({ id: 1, title: 'Track 1' }),
    duration: 180,
  },
  connection: {
    ...emptyStoreState.connection,
    wsConnected: true,
    apiConnected: true,
    latency: 25,
  },
};

/**
 * Playing state with queue
 */
export const playingWithQueueState: RootState = {
  ...emptyStoreState,
  player: {
    ...emptyStoreState.player,
    isPlaying: true,
    currentTrack: createMockTrack({ id: 1, title: 'Track 1' }),
    currentTime: 45,
    duration: 180,
  },
  queue: {
    ...emptyStoreState.queue,
    tracks: createMockTracks(5),
    currentIndex: 0,
  },
  connection: {
    ...emptyStoreState.connection,
    wsConnected: true,
    apiConnected: true,
    latency: 25,
  },
};

/**
 * Healthy cache state
 */
export const healthyCacheState: RootState = {
  ...emptyStoreState,
  cache: {
    ...emptyStoreState.cache,
    stats: createMockCacheStats(),
    health: createMockCacheHealth(),
  },
};

/**
 * Loading state
 */
export const loadingState: RootState = {
  ...emptyStoreState,
  player: {
    ...emptyStoreState.player,
    isLoading: true,
  },
  queue: {
    ...emptyStoreState.queue,
    isLoading: true,
  },
  cache: {
    ...emptyStoreState.cache,
    isLoading: true,
  },
};

/**
 * Error state
 */
export const errorState: RootState = {
  ...emptyStoreState,
  player: {
    ...emptyStoreState.player,
    error: 'Playback failed',
  },
  queue: {
    ...emptyStoreState.queue,
    error: 'Failed to load queue',
  },
  cache: {
    ...emptyStoreState.cache,
    error: 'Cache unavailable',
  },
  connection: {
    ...emptyStoreState.connection,
    lastError: 'Connection lost',
  },
};

/**
 * Offline state
 */
export const offlineState: RootState = {
  ...emptyStoreState,
  connection: {
    ...emptyStoreState.connection,
    wsConnected: false,
    apiConnected: false,
    latency: 0,
    lastError: 'Connection lost',
  },
};

/**
 * Reconnecting state
 */
export const reconnectingState: RootState = {
  ...emptyStoreState,
  connection: {
    ...emptyStoreState.connection,
    wsConnected: false,
    apiConnected: false,
    reconnectAttempts: 2,
    lastError: 'Attempting to reconnect...',
  },
};

// ============================================================================
// Store Creation Utilities
// ============================================================================

/**
 * Create test store with optional initial state
 */
export function createTestStore(initialState?: Partial<RootState>) {
  const preloadedState = initialState
    ? {
        player: { ...emptyStoreState.player, ...initialState.player },
        queue: { ...emptyStoreState.queue, ...initialState.queue },
        cache: { ...emptyStoreState.cache, ...initialState.cache },
        connection: { ...emptyStoreState.connection, ...initialState.connection },
      }
    : undefined;

  return configureStore({
    reducer: {
      player: playerReducer,
      queue: queueReducer,
      cache: cacheReducer,
      connection: connectionReducer,
    },
    preloadedState: preloadedState as RootState,
  });
}

/**
 * Create store with specific fixture
 */
export function createStoreFromFixture(fixture: RootState) {
  return configureStore({
    reducer: {
      player: playerReducer,
      queue: queueReducer,
      cache: cacheReducer,
      connection: connectionReducer,
    },
    preloadedState: fixture,
  });
}

// ============================================================================
// State Verification Helpers
// ============================================================================

/**
 * Verify player is in expected state
 */
export function assertPlayerState(
  state: RootState,
  expected: Partial<RootState['player']>
) {
  const actual = state.player;
  for (const [key, value] of Object.entries(expected)) {
    if (actual[key as keyof typeof actual] !== value) {
      throw new Error(
        `Player state mismatch: ${key} expected ${value} but got ${actual[key as keyof typeof actual]}`
      );
    }
  }
}

/**
 * Verify queue is in expected state
 */
export function assertQueueState(
  state: RootState,
  expected: Partial<RootState['queue']>
) {
  const actual = state.queue;
  if (expected.tracks && JSON.stringify(actual.tracks) !== JSON.stringify(expected.tracks)) {
    throw new Error('Queue tracks do not match');
  }
  if (expected.currentIndex !== undefined && actual.currentIndex !== expected.currentIndex) {
    throw new Error(`Queue currentIndex expected ${expected.currentIndex} but got ${actual.currentIndex}`);
  }
}

/**
 * Verify no errors in state
 */
export function assertNoErrors(state: RootState) {
  if (state.player.error) throw new Error(`Player error: ${state.player.error}`);
  if (state.queue.error) throw new Error(`Queue error: ${state.queue.error}`);
  if (state.cache.error) throw new Error(`Cache error: ${state.cache.error}`);
  if (state.connection.lastError) throw new Error(`Connection error: ${state.connection.lastError}`);
}

/**
 * Verify app is fully connected
 */
export function assertConnected(state: RootState) {
  if (!state.connection.wsConnected) throw new Error('WebSocket not connected');
  if (!state.connection.apiConnected) throw new Error('API not connected');
}

// ============================================================================
// Store Comparison Utilities
// ============================================================================

/**
 * Get differences between two states
 */
export function getStateDiff(state1: RootState, state2: RootState) {
  const diffs: Record<string, any> = {};

  const slices = Object.keys(state1) as (keyof RootState)[];
  for (const slice of slices) {
    if (JSON.stringify(state1[slice]) !== JSON.stringify(state2[slice])) {
      diffs[slice] = {
        before: state1[slice],
        after: state2[slice],
      };
    }
  }

  return diffs;
}

/**
 * Verify state changed
 */
export function assertStateChanged(before: RootState, after: RootState, expectedSlices: string[]) {
  const diffs = getStateDiff(before, after);
  for (const slice of expectedSlices) {
    if (!diffs[slice]) {
      throw new Error(`Expected ${slice} to change but it didn't`);
    }
  }
}

/**
 * Verify state unchanged
 */
export function assertStateUnchanged(before: RootState, after: RootState) {
  const diffs = getStateDiff(before, after);
  if (Object.keys(diffs).length > 0) {
    throw new Error(`Expected state to be unchanged but got changes: ${JSON.stringify(diffs)}`);
  }
}

// ============================================================================
// Common Test Scenarios
// ============================================================================

export const testScenarios = {
  empty: emptyStoreState,
  connectedWithTrack: connectedWithTrackState,
  playingWithQueue: playingWithQueueState,
  healthyCache: healthyCacheState,
  loading: loadingState,
  error: errorState,
  offline: offlineState,
  reconnecting: reconnectingState,
};

