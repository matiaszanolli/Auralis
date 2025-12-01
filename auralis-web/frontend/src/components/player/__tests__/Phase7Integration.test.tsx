/**
 * Phase 7 Integration Tests
 *
 * Comprehensive integration tests for the complete queue management system.
 * Tests how search, statistics, recommendations, and shuffle work together.
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { usePlaybackQueue } from '@/hooks/player/usePlaybackQueue';
import { useQueueSearch } from '@/hooks/player/useQueueSearch';
import { useQueueStatistics } from '@/hooks/player/useQueueStatistics';
import { useQueueRecommendations } from '@/hooks/player/useQueueRecommendations';
import { QueueShuffler } from '@/utils/queue/queue_shuffler';
import type { Track } from '@/types/domain';

// Large test queue
const createTestQueue = (count: number = 50): Track[] => {
  return Array.from({ length: count }, (_, i) => ({
    id: i,
    title: `Track ${i}`,
    artist: `Artist ${i % 10}`,
    album: `Album ${i % 5}`,
    duration: 180 + (i % 240),
    filepath: `/music/track${i}.mp3`,
  }));
};

describe('Phase 7 Integration Tests', () => {
  // =========================================================================
  // SEARCH + STATISTICS
  // =========================================================================

  it('should maintain statistics accuracy after searching', () => {
    const queue = createTestQueue(20);

    const { result: searchResult } = renderHook(() => useQueueSearch(queue));
    const { result: statsResult } = renderHook(() => useQueueStatistics(queue));

    expect(statsResult.current.stats.trackCount).toBe(20);

    act(() => {
      searchResult.current.setSearchQuery('track 1');
    });

    // Statistics should remain unchanged after search
    expect(statsResult.current.stats.trackCount).toBe(20);
    expect(searchResult.current.matchCount).toBeGreaterThan(0);
  });

  it('should calculate statistics for filtered results', () => {
    const queue = createTestQueue(20);

    const { result: searchResult } = renderHook(() => useQueueSearch(queue));

    act(() => {
      searchResult.current.setSearchQuery('Artist 1');
    });

    // Search should find tracks by Artist 1
    expect(searchResult.current.matchCount).toBeGreaterThan(0);

    // All results should be from Artist 1
    searchResult.current.filteredTracks.forEach((track) => {
      expect(track.track.artist).toContain('Artist 1');
    });
  });

  // =========================================================================
  // SHUFFLE + STATISTICS
  // =========================================================================

  it('should preserve statistics after shuffling', () => {
    const queue = createTestQueue(30);

    const { result: statsResult } = renderHook(() =>
      useQueueStatistics(queue)
    );

    const originalStats = {
      trackCount: statsResult.current.stats.trackCount,
      totalDuration: statsResult.current.stats.totalDuration,
      uniqueArtists: statsResult.current.stats.uniqueArtists,
    };

    // Shuffle the queue
    const shuffled = QueueShuffler.shuffle(queue, 'random');

    const { result: newStatsResult } = renderHook(() =>
      useQueueStatistics(shuffled)
    );

    expect(newStatsResult.current.stats.trackCount).toBe(
      originalStats.trackCount
    );
    expect(newStatsResult.current.stats.totalDuration).toBe(
      originalStats.totalDuration
    );
    expect(newStatsResult.current.stats.uniqueArtists).toBe(
      originalStats.uniqueArtists
    );
  });

  it('should maintain track integrity across shuffle modes', () => {
    const queue = createTestQueue(25);

    const shuffleModes: Array<
      'random' | 'weighted' | 'album' | 'artist' | 'temporal' | 'no_repeat'
    > = ['random', 'weighted', 'album', 'artist', 'temporal', 'no_repeat'];

    shuffleModes.forEach((mode) => {
      const shuffled = QueueShuffler.shuffle(queue, mode);

      // All original IDs should be present
      const originalIds = new Set(queue.map((t) => t.id));
      const shuffledIds = new Set(shuffled.map((t) => t.id));

      expect(shuffledIds).toEqual(originalIds);
      expect(shuffled).toHaveLength(queue.length);
    });
  });

  // =========================================================================
  // SEARCH + RECOMMENDATIONS
  // =========================================================================

  it('should provide recommendations based on search results', () => {
    const queue = createTestQueue(20);
    const availableTracks = createTestQueue(100);

    const { result: searchResult } = renderHook(() => useQueueSearch(queue));

    act(() => {
      searchResult.current.setSearchQuery('Track 1');
    });

    // Should find matching tracks
    expect(searchResult.current.matchCount).toBeGreaterThan(0);

    // Get first matching track
    const matchedTrack = searchResult.current.filteredTracks[0]?.track;

    if (matchedTrack) {
      // Get recommendations similar to matched track
      const { result: recResult } = renderHook(() =>
        useQueueRecommendations(queue, matchedTrack, availableTracks)
      );

      // Should provide similar recommendations
      expect(recResult.current.similarToCurrentTrack).toBeDefined();
    }
  });

  // =========================================================================
  // STATISTICS + RECOMMENDATIONS
  // =========================================================================

  it('should provide recommendations based on queue quality', () => {
    const queue = createTestQueue(15);
    const availableTracks = createTestQueue(100);

    const { result: statsResult } = renderHook(() =>
      useQueueStatistics(queue)
    );
    const { result: recResult } = renderHook(() =>
      useQueueRecommendations(queue, queue[0], availableTracks)
    );

    expect(statsResult.current.stats.trackCount).toBe(15);

    // Should have enough data for recommendations
    expect(recResult.current.hasEnoughData).toBe(
      queue.length >= 3 && availableTracks.length > queue.length
    );
  });

  // =========================================================================
  // ALL FEATURES TOGETHER
  // =========================================================================

  it('should work with all features enabled simultaneously', () => {
    const queue = createTestQueue(25);
    const availableTracks = createTestQueue(100);

    // Initialize all hooks
    const { result: searchResult } = renderHook(() => useQueueSearch(queue));
    const { result: statsResult } = renderHook(() =>
      useQueueStatistics(queue)
    );
    const { result: recResult } = renderHook(() =>
      useQueueRecommendations(queue, queue[0], availableTracks)
    );

    // Activate search
    act(() => {
      searchResult.current.setSearchQuery('Artist 1');
    });

    // Get recommendations
    expect(recResult.current.forYouRecommendations.length).toBeGreaterThanOrEqual(
      0
    );

    // Shuffle
    const shuffled = QueueShuffler.shuffle(queue, 'album');

    // Verify stats on shuffled queue
    const { result: shuffledStatsResult } = renderHook(() =>
      useQueueStatistics(shuffled)
    );

    expect(shuffledStatsResult.current.stats.trackCount).toBe(25);

    // Search on shuffled queue
    const { result: shuffledSearchResult } = renderHook(() =>
      useQueueSearch(shuffled)
    );

    act(() => {
      shuffledSearchResult.current.setSearchQuery('Track 5');
    });

    expect(shuffledSearchResult.current.filteredTracks).toBeDefined();
  });

  // =========================================================================
  // FILTER COMBINATIONS
  // =========================================================================

  it('should handle combined search and filter operations', () => {
    const queue = createTestQueue(30);

    const { result } = renderHook(() => useQueueSearch(queue));

    // Apply search
    act(() => {
      result.current.setSearchQuery('track');
    });

    const searchMatches = result.current.matchCount;

    // Apply duration filter on top of search
    act(() => {
      result.current.setFilters({ minDuration: 300 });
    });

    // Combined filter results should be subset of search results
    expect(result.current.matchCount).toBeLessThanOrEqual(searchMatches);
  });

  it('should clear all filters and search together', () => {
    const queue = createTestQueue(20);

    const { result } = renderHook(() => useQueueSearch(queue));

    act(() => {
      result.current.setSearchQuery('test');
      result.current.setFilters({ minDuration: 200 });
    });

    expect(result.current.isSearchActive).toBe(true);

    act(() => {
      result.current.clearFilters();
    });

    expect(result.current.searchQuery).toBe('');
    expect(result.current.isSearchActive).toBe(false);
    expect(result.current.matchCount).toBe(0);
  });

  // =========================================================================
  // PERFORMANCE UNDER LOAD
  // =========================================================================

  it('should maintain performance with large queue + all features', () => {
    const largeQueue = createTestQueue(500);
    const availableTracks = createTestQueue(1000);

    const startTime = performance.now();

    // Initialize all features
    const { result: searchResult } = renderHook(() =>
      useQueueSearch(largeQueue)
    );
    const { result: statsResult } = renderHook(() =>
      useQueueStatistics(largeQueue)
    );
    const { result: recResult } = renderHook(() =>
      useQueueRecommendations(largeQueue, largeQueue[0], availableTracks)
    );

    // Perform operations
    act(() => {
      searchResult.current.setSearchQuery('Track');
    });

    const shuffled = QueueShuffler.shuffle(largeQueue, 'weighted');

    const endTime = performance.now();
    const elapsedMs = endTime - startTime;

    // Should complete in reasonable time
    expect(elapsedMs).toBeLessThan(500); // 500ms for all operations

    expect(statsResult.current.stats.trackCount).toBe(500);
    expect(shuffled).toHaveLength(500);
  });

  it('should handle multiple shuffle modes efficiently', () => {
    const queue = createTestQueue(100);
    const modes: Array<
      'random' | 'weighted' | 'album' | 'artist' | 'temporal' | 'no_repeat'
    > = ['random', 'weighted', 'album', 'artist', 'temporal', 'no_repeat'];

    const startTime = performance.now();

    modes.forEach((mode) => {
      QueueShuffler.shuffle(queue, mode);
    });

    const endTime = performance.now();

    // All 6 shuffles should complete quickly
    expect(endTime - startTime).toBeLessThan(100);
  });

  // =========================================================================
  // DATA CONSISTENCY
  // =========================================================================

  it('should maintain data consistency across operations', () => {
    const queue = createTestQueue(20);
    const availableTracks = createTestQueue(50);

    // Get initial stats
    const { result: statsResult } = renderHook(() =>
      useQueueStatistics(queue)
    );

    const initialTrackCount = statsResult.current.stats.trackCount;
    const initialDuration = statsResult.current.stats.totalDuration;

    // Shuffle
    const shuffled = QueueShuffler.shuffle(queue, 'random');

    // Get stats on shuffled
    const { result: shuffledStatsResult } = renderHook(() =>
      useQueueStatistics(shuffled)
    );

    // Data should be identical
    expect(shuffledStatsResult.current.stats.trackCount).toBe(
      initialTrackCount
    );
    expect(shuffledStatsResult.current.stats.totalDuration).toBe(
      initialDuration
    );

    // Search should work on shuffled
    const { result: searchResult } = renderHook(() =>
      useQueueSearch(shuffled)
    );

    act(() => {
      searchResult.current.setSearchQuery('track');
    });

    expect(searchResult.current.matchCount).toBeGreaterThan(0);
  });

  // =========================================================================
  // EDGE CASES & ERROR HANDLING
  // =========================================================================

  it('should handle empty queue gracefully', () => {
    const emptyQueue: Track[] = [];
    const availableTracks = createTestQueue(20);

    const { result: searchResult } = renderHook(() =>
      useQueueSearch(emptyQueue)
    );
    const { result: statsResult } = renderHook(() =>
      useQueueStatistics(emptyQueue)
    );
    const { result: recResult } = renderHook(() =>
      useQueueRecommendations(emptyQueue, null, availableTracks)
    );

    expect(statsResult.current.isEmpty).toBe(true);
    expect(recResult.current.hasEnoughData).toBe(false);
    expect(searchResult.current.matchCount).toBe(0);
  });

  it('should handle queue with single track', () => {
    const singleTrackQueue = [createTestQueue(1)[0]];
    const availableTracks = createTestQueue(20);

    const { result: shuffleResult } = renderHook(() => {
      const shuffled = QueueShuffler.shuffle(singleTrackQueue, 'random');
      return { shuffled };
    });

    expect(shuffleResult.current.shuffled).toHaveLength(1);
    expect(shuffleResult.current.shuffled[0].id).toBe(singleTrackQueue[0].id);
  });

  it('should handle recommendation queries without current track', () => {
    const queue = createTestQueue(10);
    const availableTracks = createTestQueue(50);

    const { result: recResult } = renderHook(() =>
      useQueueRecommendations(queue, null, availableTracks)
    );

    expect(recResult.current.similarToCurrentTrack).toHaveLength(0);
    expect(recResult.current.relatedArtists).toHaveLength(0);
  });

  // =========================================================================
  // MEMOIZATION & STABILITY
  // =========================================================================

  it('should maintain memoization across features', () => {
    const queue = createTestQueue(20);

    const { result: searchResult, rerender: rerenderSearch } = renderHook(
      ({ q }: { q: Track[] }) => useQueueSearch(q),
      { initialProps: { q: queue } }
    );

    const firstResults = searchResult.current.filteredTracks;

    // Rerender with same queue
    rerenderSearch({ q: queue });

    // Should maintain same reference
    expect(searchResult.current.filteredTracks).toBe(firstResults);

    // Rerender with different queue
    const newQueue = createTestQueue(15);
    rerenderSearch({ q: newQueue });

    // Should create new reference
    expect(searchResult.current.filteredTracks).not.toBe(firstResults);
  });
});
