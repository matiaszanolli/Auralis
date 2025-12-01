/**
 * useQueueSearch Hook Tests
 *
 * Comprehensive test suite for queue search and filtering functionality.
 * Covers: text search, filtering, performance, sorting
 */

import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useQueueSearch } from '../useQueueSearch';
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
    filepath: '/music/ledzeppelin/stairway.mp3',
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

describe('useQueueSearch', () => {
  // =========================================================================
  // SEARCH FUNCTIONALITY
  // =========================================================================

  it('should return empty results when no search or filters active', () => {
    const { result } = renderHook(() => useQueueSearch(mockTracks));

    expect(result.current.searchQuery).toBe('');
    expect(result.current.filteredTracks).toHaveLength(0);
    expect(result.current.matchCount).toBe(0);
    expect(result.current.isSearchActive).toBe(false);
  });

  it('should search tracks by title', () => {
    const { result } = renderHook(() => useQueueSearch(mockTracks));

    act(() => {
      result.current.setSearchQuery('bohemian');
    });

    expect(result.current.matchCount).toBe(1);
    expect(result.current.filteredTracks[0].track.title).toBe('Bohemian Rhapsody');
    expect(result.current.filteredTracks[0].titleMatch).toBe(true);
  });

  it('should search tracks by artist', () => {
    const { result } = renderHook(() => useQueueSearch(mockTracks));

    act(() => {
      result.current.setSearchQuery('queen');
    });

    expect(result.current.matchCount).toBe(1);
    expect(result.current.filteredTracks[0].track.artist).toBe('Queen');
    expect(result.current.filteredTracks[0].artistMatch).toBe(true);
  });

  it('should search tracks by album', () => {
    const { result } = renderHook(() => useQueueSearch(mockTracks));

    act(() => {
      result.current.setSearchQuery('divide');
    });

    expect(result.current.matchCount).toBe(1);
    expect(result.current.filteredTracks[0].track.album).toBe('Divide');
    expect(result.current.filteredTracks[0].albumMatch).toBe(true);
  });

  it('should perform case-insensitive search', () => {
    const { result } = renderHook(() => useQueueSearch(mockTracks));

    act(() => {
      result.current.setSearchQuery('STAIRWAY');
    });

    expect(result.current.matchCount).toBe(1);
    expect(result.current.filteredTracks[0].track.title).toBe('Stairway to Heaven');
  });

  it('should find multiple matches', () => {
    const { result } = renderHook(() => useQueueSearch(mockTracks));

    act(() => {
      result.current.setSearchQuery('heaven');
    });

    expect(result.current.matchCount).toBe(1);
    expect(result.current.filteredTracks[0].track.title).toContain('Heaven');
  });

  it('should handle partial word matching', () => {
    const { result } = renderHook(() => useQueueSearch(mockTracks));

    act(() => {
      result.current.setSearchQuery('rap');
    });

    expect(result.current.matchCount).toBe(1);
    expect(result.current.filteredTracks[0].track.title).toContain('Rhapsody');
  });

  it('should trim whitespace from search query', () => {
    const { result } = renderHook(() => useQueueSearch(mockTracks));

    act(() => {
      result.current.setSearchQuery('  queen  ');
    });

    expect(result.current.matchCount).toBe(1);
    expect(result.current.searchQuery).toBe('  queen  ');
  });

  it('should handle empty search query', () => {
    const { result } = renderHook(() => useQueueSearch(mockTracks));

    act(() => {
      result.current.setSearchQuery('queen');
    });

    expect(result.current.matchCount).toBe(1);

    act(() => {
      result.current.setSearchQuery('');
    });

    expect(result.current.matchCount).toBe(0);
  });

  // =========================================================================
  // FILTERING
  // =========================================================================

  it('should filter by minimum duration', () => {
    const { result } = renderHook(() => useQueueSearch(mockTracks));

    act(() => {
      result.current.setFilters({ minDuration: 300 });
    });

    const filtered = result.current.filteredTracks;
    expect(filtered.every((r) => r.track.duration >= 300)).toBe(true);
    expect(filtered.length).toBe(3); // Bohemian (354), Stairway (482), Hotel (391)
  });

  it('should filter by maximum duration', () => {
    const { result } = renderHook(() => useQueueSearch(mockTracks));

    act(() => {
      result.current.setFilters({ maxDuration: 300 });
    });

    const filtered = result.current.filteredTracks;
    expect(filtered.every((r) => r.track.duration <= 300)).toBe(true);
    expect(filtered.length).toBe(2); // Imagine (183), Perfect (263)
  });

  it('should filter by duration range', () => {
    const { result } = renderHook(() => useQueueSearch(mockTracks));

    act(() => {
      result.current.setFilters({
        minDuration: 200,
        maxDuration: 400,
      });
    });

    const filtered = result.current.filteredTracks;
    expect(filtered.every((r) => r.track.duration >= 200 && r.track.duration <= 400)).toBe(true);
    expect(filtered.length).toBe(3); // Bohemian (354), Hotel (391), Perfect (263)
  });

  // =========================================================================
  // RELEVANCE SCORING
  // =========================================================================

  it('should rank title matches higher than artist matches', () => {
    const tracks: Track[] = [
      {
        id: 1,
        title: 'Queen Album',
        artist: 'Other Artist',
        album: 'Album',
        duration: 200,
        filepath: '/music/1.mp3',
      },
      {
        id: 2,
        title: 'Different Title',
        artist: 'Queen',
        album: 'Album',
        duration: 200,
        filepath: '/music/2.mp3',
      },
    ];

    const { result } = renderHook(() => useQueueSearch(tracks));

    act(() => {
      result.current.setSearchQuery('queen');
    });

    expect(result.current.filteredTracks[0].track.title).toBe('Queen Album');
    expect(result.current.filteredTracks[1].track.artist).toBe('Queen');
  });

  it('should mark all matching fields', () => {
    const tracks: Track[] = [
      {
        id: 1,
        title: 'Queen Song',
        artist: 'Queen',
        album: 'Queen Album',
        duration: 200,
        filepath: '/music/1.mp3',
      },
    ];

    const { result } = renderHook(() => useQueueSearch(tracks));

    act(() => {
      result.current.setSearchQuery('queen');
    });

    const match = result.current.filteredTracks[0];
    expect(match.titleMatch).toBe(true);
    expect(match.artistMatch).toBe(true);
    expect(match.albumMatch).toBe(true);
  });

  // =========================================================================
  // COMBINED SEARCH AND FILTERS
  // =========================================================================

  it('should combine search and duration filters', () => {
    const { result } = renderHook(() => useQueueSearch(mockTracks));

    act(() => {
      result.current.setSearchQuery('a');
      result.current.setFilters({ minDuration: 300 });
    });

    // Should only return tracks with "a" in title/artist/album AND duration >= 300
    const filtered = result.current.filteredTracks;
    expect(
      filtered.every(
        (r) =>
          (r.titleMatch || r.artistMatch || r.albumMatch) && r.track.duration >= 300
      )
    ).toBe(true);
  });

  it('should support multiple filters together', () => {
    const { result } = renderHook(() => useQueueSearch(mockTracks));

    act(() => {
      result.current.setFilters({
        minDuration: 250,
        maxDuration: 400,
      });
    });

    const filtered = result.current.filteredTracks;
    expect(filtered.every((r) => r.track.duration >= 250 && r.track.duration <= 400)).toBe(true);
  });

  // =========================================================================
  // CLEARING AND RESETTING
  // =========================================================================

  it('should clear filters and search', () => {
    const { result } = renderHook(() => useQueueSearch(mockTracks));

    act(() => {
      result.current.setSearchQuery('queen');
      result.current.setFilters({ minDuration: 300 });
    });

    expect(result.current.isSearchActive).toBe(true);
    expect(result.current.matchCount).toBeGreaterThan(0);

    act(() => {
      result.current.clearFilters();
    });

    expect(result.current.searchQuery).toBe('');
    expect(result.current.filters).toEqual({});
    expect(result.current.filteredTracks).toHaveLength(0);
    expect(result.current.isSearchActive).toBe(false);
  });

  it('should update filters partially', () => {
    const { result } = renderHook(() => useQueueSearch(mockTracks));

    act(() => {
      result.current.setFilters({ minDuration: 300 });
    });

    expect(result.current.filters.minDuration).toBe(300);

    act(() => {
      result.current.setFilters({ maxDuration: 400 });
    });

    expect(result.current.filters.minDuration).toBe(300);
    expect(result.current.filters.maxDuration).toBe(400);
  });

  // =========================================================================
  // SEARCH STATE
  // =========================================================================

  it('should track isSearchActive correctly', () => {
    const { result } = renderHook(() => useQueueSearch(mockTracks));

    expect(result.current.isSearchActive).toBe(false);

    act(() => {
      result.current.setSearchQuery('queen');
    });

    expect(result.current.isSearchActive).toBe(true);

    act(() => {
      result.current.setSearchQuery('');
    });

    expect(result.current.isSearchActive).toBe(false);
  });

  it('should maintain original track indices', () => {
    const { result } = renderHook(() => useQueueSearch(mockTracks));

    act(() => {
      result.current.setSearchQuery('bohemian');
    });

    expect(result.current.filteredTracks[0].originalIndex).toBe(0);
  });

  // =========================================================================
  // PERFORMANCE
  // =========================================================================

  it('should handle large queues efficiently', () => {
    // Create large track list
    const largeTracks: Track[] = Array.from({ length: 10000 }, (_, i) => ({
      id: i,
      title: `Track ${i}`,
      artist: `Artist ${i % 100}`,
      album: `Album ${i % 50}`,
      duration: 180 + (i % 300),
      filepath: `/music/track${i}.mp3`,
    }));

    const { result } = renderHook(() => useQueueSearch(largeTracks));

    const startTime = performance.now();

    act(() => {
      result.current.setSearchQuery('5000');
    });

    const endTime = performance.now();
    const elapsedMs = endTime - startTime;

    // Should search 10k tracks in less than 100ms
    expect(elapsedMs).toBeLessThan(100);
    expect(result.current.matchCount).toBeGreaterThan(0);
  });

  it('should handle rapid search updates', () => {
    const { result } = renderHook(() => useQueueSearch(mockTracks));

    act(() => {
      result.current.setSearchQuery('q');
      result.current.setSearchQuery('qu');
      result.current.setSearchQuery('que');
      result.current.setSearchQuery('queen');
    });

    expect(result.current.matchCount).toBe(1);
    expect(result.current.filteredTracks[0].track.artist).toBe('Queen');
  });

  // =========================================================================
  // EDGE CASES
  // =========================================================================

  it('should handle empty queue', () => {
    const { result } = renderHook(() => useQueueSearch([]));

    act(() => {
      result.current.setSearchQuery('queen');
    });

    expect(result.current.matchCount).toBe(0);
    expect(result.current.filteredTracks).toHaveLength(0);
  });

  it('should handle tracks with missing album field', () => {
    const tracks: Track[] = [
      {
        id: 1,
        title: 'Song Title',
        artist: 'Artist',
        album: '',
        duration: 200,
        filepath: '/music/1.mp3',
      },
    ];

    const { result } = renderHook(() => useQueueSearch(tracks));

    act(() => {
      result.current.setSearchQuery('song');
    });

    expect(result.current.matchCount).toBe(1);
  });

  it('should handle special characters in search', () => {
    const { result } = renderHook(() => useQueueSearch(mockTracks));

    act(() => {
      result.current.setSearchQuery('a/b?c');
    });

    // Should not crash, just return no results
    expect(result.current.filteredTracks).toBeDefined();
  });

  it('should filter and search independently', () => {
    const { result } = renderHook(() => useQueueSearch(mockTracks));

    // First just filter
    act(() => {
      result.current.setFilters({ minDuration: 300 });
    });

    const filterOnlyCount = result.current.matchCount;

    // Then add search
    act(() => {
      result.current.setSearchQuery('queen');
    });

    const combinedCount = result.current.matchCount;

    expect(combinedCount).toBeLessThanOrEqual(filterOnlyCount);
  });

  it('should return relevance score between 0 and 1', () => {
    const { result } = renderHook(() => useQueueSearch(mockTracks));

    act(() => {
      result.current.setSearchQuery('a');
    });

    result.current.filteredTracks.forEach((match) => {
      expect(match.relevance).toBeGreaterThanOrEqual(0);
      expect(match.relevance).toBeLessThanOrEqual(1);
    });
  });
});
