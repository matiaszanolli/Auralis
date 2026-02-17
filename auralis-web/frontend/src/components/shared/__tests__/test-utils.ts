/**
 * Component Test Utilities
 * ~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Shared utilities for testing Phase C.2 components including:
 * - Mock data generators
 * - Mock hooks
 * - Test helpers
 *
 * Phase C.3: Component Testing & Integration
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { vi } from 'vitest';

/**
 * Mock cache stats for testing
 */
export const mockCacheStats = {
  tier1: {
    chunks: 4,
    size_mb: 6.0,
    hits: 150,
    misses: 10,
    hit_rate: 0.938,
  },
  tier2: {
    chunks: 146,
    size_mb: 219.0,
    hits: 1350,
    misses: 90,
    hit_rate: 0.937,
  },
  overall: {
    total_chunks: 150,
    total_size_mb: 225.0,
    total_hits: 1500,
    total_misses: 100,
    overall_hit_rate: 0.938,
    tracks_cached: 5,
  },
  tracks: {
    '1': {
      track_id: 1,
      completion_percent: 100,
      fully_cached: true,
    },
    '2': {
      track_id: 2,
      completion_percent: 75,
      fully_cached: false,
    },
  },
};

/**
 * Mock cache health for testing
 */
export const mockCacheHealth = {
  healthy: true,
  tier1_size_mb: 6.0,
  tier1_healthy: true,
  tier2_size_mb: 200.0,
  tier2_healthy: true,
  total_size_mb: 206.0,
  memory_healthy: true,
  tier1_hit_rate: 0.95,
  overall_hit_rate: 0.95,  // 95% hit rate
  timestamp: new Date().toISOString(),
};

/**
 * Mock unhealthy cache for testing
 */
export const mockUnhealthyCacheHealth = {
  healthy: false,
  tier1_size_mb: 15.0,
  tier1_healthy: false,
  tier2_size_mb: 250.0,
  tier2_healthy: false,
  total_size_mb: 265.0,
  memory_healthy: false,
  tier1_hit_rate: 0.45,
  overall_hit_rate: 0.48,
  timestamp: new Date().toISOString(),
};

/**
 * Mock track for testing
 */
export const mockTrack = {
  id: 1,
  title: 'Test Track',
  artist: 'Test Artist',
  album: 'Test Album',
  duration: 240,
  artworkUrl: 'https://example.com/cover.jpg',
};

/**
 * Generate mock tracks
 */
export function mockTracks(count: number = 3) {
  const tracks = [
    { ...mockTrack, id: 1, title: 'Track 1', artist: 'Artist 1', duration: 180 },
    { ...mockTrack, id: 2, title: 'Track 2', artist: 'Artist 2', duration: 180 },
    { ...mockTrack, id: 3, title: 'Track 3', artist: 'Artist 3', duration: 180 },
  ];
  return tracks.slice(0, count);
}

/**
 * Mock player state hook response
 */
export const mockUsePlayerState = {
  isPlaying: false,
  currentTrack: mockTrack,
  currentTime: 0,
  duration: 240,
  volume: 70,
  isMuted: false,
  preset: 'adaptive' as const,
  isLoading: false,
  error: null,
};

/**
 * Create mock useCacheStats hook
 */
export function mockUseCacheStats(overrides = {}) {
  return vi.fn().mockReturnValue({
    data: { ...mockCacheStats, ...overrides },
    loading: false,
    error: null,
    refetch: vi.fn().mockResolvedValue(undefined),
  });
}

/**
 * Create mock useCacheHealth hook
 */
export function mockUseCacheHealth(overrides = {}) {
  return vi.fn().mockReturnValue({
    data: { ...mockCacheHealth, ...overrides },
    loading: false,
    error: null,
    isHealthy: true,
    refetch: vi.fn().mockResolvedValue(undefined),
  });
}

/**
 * Create mock useStandardizedAPI hook
 */
export function mockUseStandardizedAPI(overrides = {}) {
  return vi.fn().mockReturnValue({
    data: null,
    loading: false,
    error: null,
    refetch: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  });
}

/**
 * Create mock usePlayerCommands hook
 */
export function mockUsePlayerCommands() {
  return {
    play: vi.fn().mockResolvedValue(undefined),
    pause: vi.fn().mockResolvedValue(undefined),
    seek: vi.fn().mockResolvedValue(undefined),
    next: vi.fn().mockResolvedValue(undefined),
    previous: vi.fn().mockResolvedValue(undefined),
  };
}

/**
 * Create mock useQueueCommands hook
 */
export function mockUseQueueCommands() {
  return {
    add: vi.fn().mockResolvedValue(undefined),
    remove: vi.fn().mockResolvedValue(undefined),
    clear: vi.fn().mockResolvedValue(undefined),
    reorder: vi.fn().mockResolvedValue(undefined),
    tracks: mockTracks(3),
    currentIndex: 0,
    loading: false,
    error: null,
  };
}

/**
 * Create mock useWebSocketProtocol hook
 */
export function mockUseWebSocketProtocol(overrides = {}) {
  return {
    connected: true,
    error: null,
    send: vi.fn().mockResolvedValue(undefined),
    subscribe: vi.fn().mockReturnValue(vi.fn()),
    disconnect: vi.fn(),
    reconnect: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

/**
 * Create mock usePlayerStateUpdates hook
 */
export function mockUsePlayerStateUpdates() {
  return vi.fn((callback) => {
    // Return immediately without calling the callback
    // This simulates the subscription hook without triggering updates
  });
}

/**
 * Create mock useCacheStatsUpdates hook
 */
export function mockUseCacheStatsUpdates() {
  return vi.fn();
}

/**
 * Wait for async operations
 */
export async function waitForAsync() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

/**
 * Format time for testing
 */
export function formatTime(seconds: number): string {
  if (!isFinite(seconds)) return '0:00';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}
