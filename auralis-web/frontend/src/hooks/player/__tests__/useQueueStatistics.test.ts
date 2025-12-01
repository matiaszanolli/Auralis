/**
 * useQueueStatistics Hook Tests
 *
 * Comprehensive test suite for queue statistics hook.
 * Covers: calculations, memoization, distributions, quality assessment
 */

import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useQueueStatistics } from '../useQueueStatistics';
import type { Track } from '@/types/domain';

// Mock tracks for testing
const mockTracks: Track[] = [
  {
    id: 1,
    title: 'Bohemian Rhapsody',
    artist: 'Queen',
    album: 'A Night at the Opera',
    duration: 354,
    filepath: '/music/queen/bohemian.mp3',
  },
  {
    id: 2,
    title: 'Stairway to Heaven',
    artist: 'Led Zeppelin',
    album: 'Led Zeppelin IV',
    duration: 482,
    filepath: '/music/ledzeppelin/stairway.flac',
  },
  {
    id: 3,
    title: 'Imagine',
    artist: 'John Lennon',
    album: 'Imagine',
    duration: 183,
    filepath: '/music/johnlennon/imagine.mp3',
  },
  {
    id: 4,
    title: 'Hotel California',
    artist: 'Eagles',
    album: 'Hotel California',
    duration: 391,
    filepath: '/music/eagles/hotel.mp3',
  },
  {
    id: 5,
    title: 'Perfect',
    artist: 'Ed Sheeran',
    album: 'Divide',
    duration: 263,
    filepath: '/music/edsheeran/perfect.mp3',
  },
];

describe('useQueueStatistics', () => {
  // =========================================================================
  // BASIC STATS
  // =========================================================================

  it('should return stats object', () => {
    const { result } = renderHook(() => useQueueStatistics(mockTracks));

    expect(result.current.stats).toBeDefined();
    expect(result.current.stats.trackCount).toBe(5);
  });

  it('should calculate total duration', () => {
    const { result } = renderHook(() => useQueueStatistics(mockTracks));

    const expectedTotal = 354 + 482 + 183 + 391 + 263;
    expect(result.current.stats.totalDuration).toBe(expectedTotal);
  });

  it('should calculate average duration', () => {
    const { result } = renderHook(() => useQueueStatistics(mockTracks));

    const expectedTotal = 354 + 482 + 183 + 391 + 263;
    const expectedAverage = expectedTotal / 5;
    expect(result.current.stats.averageDuration).toBeCloseTo(expectedAverage, 2);
  });

  it('should provide estimated play time', () => {
    const { result } = renderHook(() => useQueueStatistics(mockTracks));

    expect(result.current.stats.estimatedPlayTime).toBeTruthy();
    expect(result.current.stats.estimatedPlayTime).toMatch(/\d+[hms]/);
  });

  // =========================================================================
  // TOP ITEMS
  // =========================================================================

  it('should provide top artists', () => {
    const { result } = renderHook(() => useQueueStatistics(mockTracks));

    expect(result.current.topArtists).toBeDefined();
    expect(result.current.topArtists.length).toBeGreaterThan(0);
    expect(result.current.topArtists[0]).toHaveProperty('value');
    expect(result.current.topArtists[0]).toHaveProperty('count');
    expect(result.current.topArtists[0]).toHaveProperty('percentage');
  });

  it('should provide top albums', () => {
    const { result } = renderHook(() => useQueueStatistics(mockTracks));

    expect(result.current.topAlbums).toBeDefined();
    expect(result.current.topAlbums.length).toBeGreaterThan(0);
  });

  it('should provide top formats', () => {
    const { result } = renderHook(() => useQueueStatistics(mockTracks));

    expect(result.current.topFormats).toBeDefined();
    expect(result.current.topFormats.length).toBeGreaterThan(0);
  });

  it('should provide genres', () => {
    const { result } = renderHook(() => useQueueStatistics(mockTracks));

    expect(result.current.genres).toBeDefined();
    expect(Array.isArray(result.current.genres)).toBe(true);
  });

  // =========================================================================
  // QUALITY ASSESSMENT
  // =========================================================================

  it('should provide quality rating', () => {
    const { result } = renderHook(() => useQueueStatistics(mockTracks));

    expect(result.current.qualityRating).toBeDefined();
    expect(result.current.qualityRating.rating).toMatch(
      /excellent|good|fair|poor/
    );
    expect(Array.isArray(result.current.qualityRating.issues)).toBe(true);
  });

  it('should rate normal queue as good or excellent', () => {
    const { result } = renderHook(() => useQueueStatistics(mockTracks));

    expect(['excellent', 'good']).toContain(result.current.qualityRating.rating);
  });

  it('should flag empty queue as poor', () => {
    const { result } = renderHook(() => useQueueStatistics([]));

    expect(result.current.qualityRating.rating).toBe('poor');
    expect(result.current.qualityRating.issues.length).toBeGreaterThan(0);
  });

  // =========================================================================
  // UTILITIES
  // =========================================================================

  it('should provide getDistributionPercentages function', () => {
    const { result } = renderHook(() => useQueueStatistics(mockTracks));

    const percentages = result.current.getDistributionPercentages(
      result.current.stats.artists
    );
    expect(percentages).toBeInstanceOf(Map);
    expect(percentages.size).toBeGreaterThan(0);
  });

  it('should provide compareWith function', () => {
    const { result } = renderHook(() => useQueueStatistics(mockTracks));

    const otherQueue = mockTracks.slice(0, 3);
    const comparison = result.current.compareWith(otherQueue);

    expect(comparison).toHaveProperty('added');
    expect(comparison).toHaveProperty('removed');
    expect(comparison).toHaveProperty('moved');
    expect(comparison).toHaveProperty('similarity');
  });

  // =========================================================================
  // EMPTY QUEUE
  // =========================================================================

  it('should handle empty queue', () => {
    const { result } = renderHook(() => useQueueStatistics([]));

    expect(result.current.isEmpty).toBe(true);
    expect(result.current.stats.trackCount).toBe(0);
  });

  it('should mark non-empty queue as not empty', () => {
    const { result } = renderHook(() => useQueueStatistics(mockTracks));

    expect(result.current.isEmpty).toBe(false);
  });

  // =========================================================================
  // MEMOIZATION
  // =========================================================================

  it('should memoize stats calculation', () => {
    const { result, rerender } = renderHook(
      ({ tracks }: { tracks: Track[] }) => useQueueStatistics(tracks),
      {
        initialProps: { tracks: mockTracks },
      }
    );

    const firstStats = result.current.stats;

    // Same tracks, should return same object reference
    rerender({ tracks: mockTracks });
    const secondStats = result.current.stats;

    expect(firstStats).toBe(secondStats);
  });

  it('should recalculate on queue change', () => {
    const { result, rerender } = renderHook(
      ({ tracks }: { tracks: Track[] }) => useQueueStatistics(tracks),
      {
        initialProps: { tracks: mockTracks },
      }
    );

    const firstStats = result.current.stats;

    // Different queue
    const newQueue = mockTracks.slice(0, 3);
    rerender({ tracks: newQueue });
    const secondStats = result.current.stats;

    expect(firstStats).not.toBe(secondStats);
    expect(secondStats.trackCount).toBe(3);
  });

  // =========================================================================
  // PERCENTAGES
  // =========================================================================

  it('should calculate correct percentages', () => {
    const tracks: Track[] = [
      {
        id: 1,
        title: 'Song 1',
        artist: 'Artist A',
        album: 'Album',
        duration: 180,
        filepath: '/music/1.mp3',
      },
      {
        id: 2,
        title: 'Song 2',
        artist: 'Artist A',
        album: 'Album',
        duration: 180,
        filepath: '/music/2.mp3',
      },
      {
        id: 3,
        title: 'Song 3',
        artist: 'Artist B',
        album: 'Album',
        duration: 180,
        filepath: '/music/3.mp3',
      },
    ];

    const { result } = renderHook(() => useQueueStatistics(tracks));

    expect(result.current.topArtists[0].percentage).toBeCloseTo(66.67, 1);
  });

  // =========================================================================
  // EDGE CASES
  // =========================================================================

  it('should handle single track queue', () => {
    const singleTrack = [mockTracks[0]];
    const { result } = renderHook(() => useQueueStatistics(singleTrack));

    expect(result.current.stats.trackCount).toBe(1);
    expect(result.current.stats.minDuration).toBe(result.current.stats.maxDuration);
  });

  it('should handle very long queue', () => {
    const largeTracks: Track[] = Array.from({ length: 1000 }, (_, i) => ({
      id: i,
      title: `Track ${i}`,
      artist: `Artist ${i % 50}`,
      album: `Album ${i % 25}`,
      duration: 180 + (i % 300),
      filepath: `/music/track${i}.mp3`,
    }));

    const { result } = renderHook(() => useQueueStatistics(largeTracks));

    expect(result.current.stats.trackCount).toBe(1000);
    expect(result.current.topArtists.length).toBeLessThanOrEqual(5);
  });

  // =========================================================================
  // TOP ITEMS SORTING
  // =========================================================================

  it('should sort top artists by count descending', () => {
    const { result } = renderHook(() => useQueueStatistics(mockTracks));

    for (let i = 0; i < result.current.topArtists.length - 1; i++) {
      expect(result.current.topArtists[i].count).toBeGreaterThanOrEqual(
        result.current.topArtists[i + 1].count
      );
    }
  });

  it('should limit top artists to 5 items', () => {
    const manyTracks: Track[] = Array.from({ length: 20 }, (_, i) => ({
      id: i,
      title: `Track ${i}`,
      artist: `Artist ${i}`,
      album: `Album ${i}`,
      duration: 180,
      filepath: `/music/track${i}.mp3`,
    }));

    const { result } = renderHook(() => useQueueStatistics(manyTracks));

    expect(result.current.topArtists.length).toBeLessThanOrEqual(5);
  });

  // =========================================================================
  // COMPARISON UTILITIES
  // =========================================================================

  it('should detect added tracks in comparison', () => {
    const { result } = renderHook(() => useQueueStatistics(mockTracks));

    const smallerQueue = mockTracks.slice(0, 3);
    const comparison = result.current.compareWith(smallerQueue);

    expect(comparison.added).toBe(2);
  });

  it('should calculate similarity for identical queues', () => {
    const { result } = renderHook(() => useQueueStatistics(mockTracks));

    const comparison = result.current.compareWith(mockTracks);

    expect(comparison.similarity).toBe(1);
  });

  it('should handle comparison with empty queue', () => {
    const { result } = renderHook(() => useQueueStatistics(mockTracks));

    const comparison = result.current.compareWith([]);

    expect(comparison.added).toBe(0);
    expect(comparison.removed).toBe(5);
  });
});
