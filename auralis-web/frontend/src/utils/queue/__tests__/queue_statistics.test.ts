/**
 * Queue Statistics Utility Tests
 *
 * Comprehensive test suite for queue statistics calculations.
 * Covers: basic stats, distributions, quality assessment, comparisons
 */

import { describe, it, expect } from 'vitest';
import { QueueStatistics } from '../queue_statistics';
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

describe('QueueStatistics', () => {
  // =========================================================================
  // BASIC STATISTICS
  // =========================================================================

  it('should calculate track count', () => {
    const stats = QueueStatistics.calculateStats(mockTracks);
    expect(stats.trackCount).toBe(5);
  });

  it('should calculate total duration', () => {
    const stats = QueueStatistics.calculateStats(mockTracks);
    const expectedTotal = 354 + 482 + 183 + 391 + 263;
    expect(stats.totalDuration).toBe(expectedTotal);
  });

  it('should calculate average duration', () => {
    const stats = QueueStatistics.calculateStats(mockTracks);
    const expectedTotal = 354 + 482 + 183 + 391 + 263;
    const expectedAverage = expectedTotal / 5;
    expect(stats.averageDuration).toBeCloseTo(expectedAverage, 2);
  });

  it('should calculate min and max duration', () => {
    const stats = QueueStatistics.calculateStats(mockTracks);
    expect(stats.minDuration).toBe(183); // Imagine
    expect(stats.maxDuration).toBe(482); // Stairway to Heaven
  });

  it('should calculate median duration', () => {
    const stats = QueueStatistics.calculateStats(mockTracks);
    // Sorted: 183, 263, 354, 391, 482 → median is 354
    expect(stats.medianDuration).toBe(354);
  });

  it('should count unique artists', () => {
    const stats = QueueStatistics.calculateStats(mockTracks);
    expect(stats.uniqueArtists).toBe(5); // All different artists
  });

  it('should count unique albums', () => {
    const stats = QueueStatistics.calculateStats(mockTracks);
    expect(stats.uniqueAlbums).toBe(5); // All different albums
  });

  it('should format estimated play time', () => {
    const stats = QueueStatistics.calculateStats(mockTracks);
    expect(stats.estimatedPlayTime).toBeTruthy();
    expect(stats.estimatedPlayTime).toMatch(/^\d+[hms]\s?\d*[ms]?$/);
  });

  // =========================================================================
  // EMPTY QUEUE
  // =========================================================================

  it('should handle empty queue', () => {
    const stats = QueueStatistics.calculateStats([]);
    expect(stats.isEmpty).toBe(true);
    expect(stats.trackCount).toBe(0);
    expect(stats.totalDuration).toBe(0);
    expect(stats.uniqueArtists).toBe(0);
  });

  it('should mark non-empty queue as not empty', () => {
    const stats = QueueStatistics.calculateStats(mockTracks);
    expect(stats.isEmpty).toBe(false);
  });

  // =========================================================================
  // DISTRIBUTIONS
  // =========================================================================

  it('should build artist distribution', () => {
    const stats = QueueStatistics.calculateStats(mockTracks);
    expect(stats.artists.unique).toBe(5);
    expect(stats.artists.distribution.size).toBe(5);
  });

  it('should identify mode in distribution', () => {
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

    const stats = QueueStatistics.calculateStats(tracks);
    expect(stats.artists.mode).toBe('Artist A'); // Appears twice
  });

  it('should build format distribution', () => {
    const stats = QueueStatistics.calculateStats(mockTracks);
    expect(stats.formats.distribution.size).toBeGreaterThan(0);
    // Should have mp3 and flac
    expect(stats.formats.distribution.get('mp3')).toBeGreaterThan(0);
    expect(stats.formats.distribution.get('flac')).toBeGreaterThan(0);
  });

  // =========================================================================
  // TOP ITEMS
  // =========================================================================

  it('should get top items from distribution', () => {
    const stats = QueueStatistics.calculateStats(mockTracks);
    const topArtists = QueueStatistics.getTopItems(stats.artists, 3);
    expect(topArtists.length).toBeLessThanOrEqual(3);
    expect(topArtists[0][1]).toBeGreaterThanOrEqual(topArtists[1]?.[1] || 0);
  });

  it('should handle requesting more items than available', () => {
    const stats = QueueStatistics.calculateStats(mockTracks);
    const topArtists = QueueStatistics.getTopItems(stats.artists, 100);
    expect(topArtists.length).toBe(5); // Only 5 unique artists
  });

  // =========================================================================
  // PERCENTAGES
  // =========================================================================

  it('should calculate distribution percentages', () => {
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

    const stats = QueueStatistics.calculateStats(tracks);
    const percentages = QueueStatistics.getDistributionPercentages(
      stats.artists,
      tracks.length
    );

    expect(percentages.get('Artist A')).toBeCloseTo(66.67, 1);
    expect(percentages.get('Artist B')).toBeCloseTo(33.33, 1);
  });

  // =========================================================================
  // QUALITY ASSESSMENT
  // =========================================================================

  it('should assess queue quality as excellent for normal queue', () => {
    const stats = QueueStatistics.calculateStats(mockTracks);
    const assessment = QueueStatistics.assessPlayQuality(stats);
    expect(['excellent', 'good']).toContain(assessment.rating);
  });

  it('should flag very short tracks', () => {
    const tracks: Track[] = [
      {
        id: 1,
        title: 'Short Song',
        artist: 'Artist',
        album: 'Album',
        duration: 5,
        filepath: '/music/short.mp3',
      },
    ];

    const stats = QueueStatistics.calculateStats(tracks);
    const assessment = QueueStatistics.assessPlayQuality(stats);
    expect(assessment.issues.length).toBeGreaterThan(0);
    expect(assessment.issues[0]).toMatch(/[Ss]hort/);
  });

  it('should flag very long tracks', () => {
    const tracks: Track[] = [
      {
        id: 1,
        title: 'Long Song',
        artist: 'Artist',
        album: 'Album',
        duration: 1000,
        filepath: '/music/long.mp3',
      },
    ];

    const stats = QueueStatistics.calculateStats(tracks);
    const assessment = QueueStatistics.assessPlayQuality(stats);
    expect(assessment.issues.length).toBeGreaterThan(0);
  });

  it('should flag highly variable track lengths', () => {
    // To trigger variance > 3: (max - min) / average > 3
    // With [15, 15, 15, 700]: average = 186.25, variance = 685/186.25 = 3.68 > 3
    const tracks: Track[] = [
      {
        id: 1,
        title: 'Short 1',
        artist: 'Artist A',
        album: 'Album',
        duration: 15,
        filepath: '/music/1.mp3',
      },
      {
        id: 2,
        title: 'Short 2',
        artist: 'Artist B',
        album: 'Album',
        duration: 15,
        filepath: '/music/2.mp3',
      },
      {
        id: 3,
        title: 'Short 3',
        artist: 'Artist C',
        album: 'Album',
        duration: 15,
        filepath: '/music/3.mp3',
      },
      {
        id: 4,
        title: 'Very Long',
        artist: 'Artist D',
        album: 'Album',
        duration: 700,
        filepath: '/music/4.mp3',
      },
    ];

    const stats = QueueStatistics.calculateStats(tracks);
    const assessment = QueueStatistics.assessPlayQuality(stats);
    // Should flag for high variance and possibly very long tracks (> 600s)
    expect(['poor', 'fair', 'good']).toContain(assessment.rating);
    expect(assessment.issues.length).toBeGreaterThan(0);
  });

  it('should flag empty queue as poor quality', () => {
    const stats = QueueStatistics.calculateStats([]);
    const assessment = QueueStatistics.assessPlayQuality(stats);
    expect(assessment.rating).toBe('poor');
    expect(assessment.issues).toContain('Queue is empty');
  });

  // =========================================================================
  // QUEUE COMPARISON
  // =========================================================================

  it('should detect added tracks', () => {
    const queue1 = mockTracks.slice(0, 3);
    const queue2 = mockTracks;

    const comparison = QueueStatistics.compareQueues(queue1, queue2);
    expect(comparison.addedTracks.length).toBe(2);
  });

  it('should detect removed tracks', () => {
    const queue1 = mockTracks;
    const queue2 = mockTracks.slice(0, 3);

    const comparison = QueueStatistics.compareQueues(queue1, queue2);
    expect(comparison.removedTracks.length).toBe(2);
  });

  it('should detect moved tracks', () => {
    const queue1 = mockTracks;
    const queue2 = [
      mockTracks[2],
      mockTracks[0],
      mockTracks[1],
      mockTracks[3],
      mockTracks[4],
    ];

    const comparison = QueueStatistics.compareQueues(queue1, queue2);
    expect(comparison.movedTracks.length).toBeGreaterThan(0);
  });

  it('should calculate similarity correctly', () => {
    const queue1 = mockTracks.slice(0, 3);
    const queue2 = mockTracks.slice(0, 3);

    const comparison = QueueStatistics.compareQueues(queue1, queue2);
    expect(comparison.similarity).toBe(1); // Identical queues
  });

  it('should calculate low similarity for different queues', () => {
    const queue1 = mockTracks.slice(0, 1);
    const queue2 = mockTracks.slice(4, 5);

    const comparison = QueueStatistics.compareQueues(queue1, queue2);
    expect(comparison.similarity).toBeLessThan(0.5);
  });

  // =========================================================================
  // EDGE CASES
  // =========================================================================

  it('should handle single track queue', () => {
    const tracks: Track[] = [mockTracks[0]];
    const stats = QueueStatistics.calculateStats(tracks);

    expect(stats.trackCount).toBe(1);
    expect(stats.minDuration).toBe(stats.maxDuration);
    expect(stats.medianDuration).toBe(mockTracks[0].duration);
  });

  it('should handle duplicate artists', () => {
    const tracks: Track[] = [
      mockTracks[0],
      { ...mockTracks[1], artist: 'Queen' }, // Different track, same artist
    ];

    const stats = QueueStatistics.calculateStats(tracks);
    expect(stats.uniqueArtists).toBe(1);
    expect(stats.artists.mode).toBe('Queen');
  });

  it('should handle missing album field', () => {
    const tracks: Track[] = [
      { ...mockTracks[0], album: '' },
    ];

    const stats = QueueStatistics.calculateStats(tracks);
    expect(stats.albumDistribution).toBeDefined();
  });

  // =========================================================================
  // PERFORMANCE
  // =========================================================================

  it('should handle large queue efficiently', () => {
    const largeTracks: Track[] = Array.from({ length: 1000 }, (_, i) => ({
      id: i,
      title: `Track ${i}`,
      artist: `Artist ${i % 50}`,
      album: `Album ${i % 25}`,
      duration: 180 + (i % 300),
      filepath: `/music/track${i}.mp3`,
    }));

    const startTime = performance.now();
    const stats = QueueStatistics.calculateStats(largeTracks);
    const endTime = performance.now();

    expect(stats.trackCount).toBe(1000);
    expect(endTime - startTime).toBeLessThan(50); // Should be fast
  });

  it('should handle comparison of large queues', () => {
    const queue1: Track[] = Array.from({ length: 500 }, (_, i) => ({
      id: i,
      title: `Track ${i}`,
      artist: `Artist ${i % 50}`,
      album: `Album ${i % 25}`,
      duration: 180 + (i % 300),
      filepath: `/music/track${i}.mp3`,
    }));

    const queue2: Track[] = Array.from({ length: 500 }, (_, i) => ({
      id: i + 250,
      title: `Track ${i + 250}`,
      artist: `Artist ${(i + 250) % 50}`,
      album: `Album ${(i + 250) % 25}`,
      duration: 180 + ((i + 250) % 300),
      filepath: `/music/track${i + 250}.mp3`,
    }));

    const startTime = performance.now();
    const comparison = QueueStatistics.compareQueues(queue1, queue2);
    const endTime = performance.now();

    expect(comparison.similarity).toBeGreaterThan(0);
    expect(endTime - startTime).toBeLessThan(50);
  });
});
