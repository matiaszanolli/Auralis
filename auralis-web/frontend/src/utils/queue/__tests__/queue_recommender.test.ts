/**
 * Queue Recommender Utility Tests
 *
 * Comprehensive test suite for recommendation engine.
 * Covers: similarity scoring, recommendations, discovery
 */

import { describe, it, expect } from 'vitest';
import { QueueRecommender } from '../queue_recommender';
import type { Track } from '@/types/domain';

// Mock tracks for testing
const mockTracks: Track[] = [
  {
    id: 1,
    title: 'Song 1',
    artist: 'Artist A',
    album: 'Album 1',
    duration: 300,
    filepath: '/music/a1.mp3',
  },
  {
    id: 2,
    title: 'Song 2',
    artist: 'Artist A',
    album: 'Album 1',
    duration: 320,
    filepath: '/music/a2.mp3',
  },
  {
    id: 3,
    title: 'Song 3',
    artist: 'Artist A',
    album: 'Album 2',
    duration: 280,
    filepath: '/music/a3.mp3',
  },
  {
    id: 4,
    title: 'Song 4',
    artist: 'Artist B',
    album: 'Album 3',
    duration: 290,
    filepath: '/music/b1.mp3',
  },
  {
    id: 5,
    title: 'Song 5',
    artist: 'Artist B',
    album: 'Album 3',
    duration: 310,
    filepath: '/music/b2.flac',
  },
  {
    id: 6,
    title: 'Song 6',
    artist: 'Artist C',
    album: 'Album 4',
    duration: 330,
    filepath: '/music/c1.mp3',
  },
];

describe('QueueRecommender', () => {
  // =========================================================================
  // SIMILARITY CALCULATION
  // =========================================================================

  it('should calculate similarity between identical artists', () => {
    const result = QueueRecommender.calculateSimilarity(mockTracks[0], mockTracks[1]);

    expect(result.score).toBeGreaterThan(0.5);
    expect(result.factors.artist).toBe(1.0);
  });

  it('should calculate similarity between different artists', () => {
    const result = QueueRecommender.calculateSimilarity(mockTracks[0], mockTracks[3]);

    expect(result.score).toBeLessThan(0.5);
    expect(result.factors.artist).toBe(0.0);
  });

  it('should give bonus for same album', () => {
    const result = QueueRecommender.calculateSimilarity(mockTracks[0], mockTracks[1]);

    expect(result.factors.album).toBe(1.0);
  });

  it('should score duration similarity', () => {
    const result = QueueRecommender.calculateSimilarity(mockTracks[0], mockTracks[1]);

    expect(result.factors.duration).toBeGreaterThan(0.8);
  });

  it('should score format similarity', () => {
    const result = QueueRecommender.calculateSimilarity(mockTracks[4], mockTracks[5]);

    expect(result.factors.format).toBe(0.0); // flac vs mp3
  });

  it('should apply custom weights', () => {
    const result1 = QueueRecommender.calculateSimilarity(
      mockTracks[0],
      mockTracks[3],
      { artist: 1.0, album: 0, format: 0, duration: 0 }
    );

    const result2 = QueueRecommender.calculateSimilarity(
      mockTracks[0],
      mockTracks[3],
      { artist: 0, album: 0, format: 0, duration: 1.0 }
    );

    expect(result1.score).not.toBe(result2.score);
  });

  // =========================================================================
  // SIMILAR TRACKS RECOMMENDATION
  // =========================================================================

  it('should recommend similar tracks', () => {
    const recommendations = QueueRecommender.recommendSimilarTracks(
      mockTracks[0],
      mockTracks,
      5
    );

    expect(recommendations.length).toBeGreaterThan(0);
    expect(recommendations[0].track.id).not.toBe(mockTracks[0].id);
  });

  it('should not recommend seed track itself', () => {
    const recommendations = QueueRecommender.recommendSimilarTracks(
      mockTracks[0],
      mockTracks,
      5
    );

    expect(recommendations.every((r) => r.track.id !== mockTracks[0].id)).toBe(true);
  });

  it('should sort recommendations by score', () => {
    const recommendations = QueueRecommender.recommendSimilarTracks(
      mockTracks[0],
      mockTracks,
      5
    );

    for (let i = 0; i < recommendations.length - 1; i++) {
      expect(recommendations[i].score).toBeGreaterThanOrEqual(
        recommendations[i + 1].score
      );
    }
  });

  it('should respect minScore option', () => {
    const recommendations = QueueRecommender.recommendSimilarTracks(
      mockTracks[0],
      mockTracks,
      5,
      { minScore: 0.8 }
    );

    expect(recommendations.every((r) => r.score >= 0.8)).toBe(true);
  });

  it('should limit results to requested count', () => {
    const recommendations = QueueRecommender.recommendSimilarTracks(
      mockTracks[0],
      mockTracks,
      2
    );

    expect(recommendations.length).toBeLessThanOrEqual(2);
  });

  it('should provide recommendation reason', () => {
    const recommendations = QueueRecommender.recommendSimilarTracks(
      mockTracks[0],
      mockTracks,
      5
    );

    expect(recommendations[0].reason).toBeTruthy();
  });

  // =========================================================================
  // FOR YOU RECOMMENDATIONS
  // =========================================================================

  it('should recommend for you based on queue', () => {
    const queue = [mockTracks[0], mockTracks[1]];
    const recommendations = QueueRecommender.recommendForYou(
      queue,
      mockTracks,
      5
    );

    expect(recommendations.length).toBeGreaterThan(0);
  });

  it('should not recommend tracks in queue', () => {
    const queue = [mockTracks[0], mockTracks[1]];
    const recommendations = QueueRecommender.recommendForYou(
      queue,
      mockTracks,
      5,
      { excludeQueue: true }
    );

    const queueIds = new Set(queue.map((t) => t.id));
    expect(recommendations.every((r) => !queueIds.has(r.track.id))).toBe(true);
  });

  it('should handle empty queue', () => {
    const recommendations = QueueRecommender.recommendForYou([], mockTracks, 5);

    expect(recommendations).toHaveLength(0);
  });

  // =========================================================================
  // ARTIST-BASED RECOMMENDATIONS
  // =========================================================================

  it('should get tracks by artist', () => {
    const tracks = QueueRecommender.getByArtist('Artist A', mockTracks);

    expect(tracks.length).toBe(3);
    expect(tracks.every((t) => t.artist === 'Artist A')).toBe(true);
  });

  it('should be case-insensitive for artist', () => {
    const tracks1 = QueueRecommender.getByArtist('Artist A', mockTracks);
    const tracks2 = QueueRecommender.getByArtist('artist a', mockTracks);

    expect(tracks1.length).toBe(tracks2.length);
  });

  it('should get albums by artist', () => {
    const albums = QueueRecommender.getAlbumsByArtist('Artist A', mockTracks);

    expect(albums.size).toBe(2);
    expect(albums.get('Album 1')).toHaveLength(2);
    expect(albums.get('Album 2')).toHaveLength(1);
  });

  it('should return empty for non-existent artist', () => {
    const tracks = QueueRecommender.getByArtist('Nonexistent', mockTracks);

    expect(tracks).toHaveLength(0);
  });

  // =========================================================================
  // DISCOVERY
  // =========================================================================

  it('should discover new artists', () => {
    const queue = [mockTracks[0]];
    const newArtists = QueueRecommender.discoverNewArtists(queue, mockTracks, 5);

    expect(newArtists.length).toBeGreaterThan(0);
    expect(newArtists[0].artist).not.toBe('Artist A');
  });

  it('should exclude queue artists from discovery', () => {
    const queue = [mockTracks[0]];
    const newArtists = QueueRecommender.discoverNewArtists(queue, mockTracks, 5);

    expect(newArtists.every((a) => a.artist !== 'Artist A')).toBe(true);
  });

  it('should include track samples in discovery', () => {
    const queue = [mockTracks[0]];
    const newArtists = QueueRecommender.discoverNewArtists(queue, mockTracks, 5);

    expect(newArtists[0].tracks.length).toBeGreaterThan(0);
  });

  // =========================================================================
  // RELATED ARTISTS
  // =========================================================================

  it('should find related artists', () => {
    const queue = [mockTracks[0], mockTracks[1]];
    const related = QueueRecommender.findRelatedArtists(
      'Artist A',
      queue,
      mockTracks,
      5
    );

    expect(Array.isArray(related)).toBe(true);
  });

  it('should exclude seed artist from related', () => {
    const queue = [mockTracks[0]];
    const related = QueueRecommender.findRelatedArtists(
      'Artist A',
      queue,
      mockTracks,
      5
    );

    expect(related.every((a) => a.artist !== 'Artist A')).toBe(true);
  });

  it('should sort related artists by similarity', () => {
    const queue = [mockTracks[0], mockTracks[1], mockTracks[3]];
    const related = QueueRecommender.findRelatedArtists(
      'Artist A',
      queue,
      mockTracks,
      5
    );

    for (let i = 0; i < related.length - 1; i++) {
      expect(related[i].similarity).toBeGreaterThanOrEqual(
        related[i + 1].similarity
      );
    }
  });

  // =========================================================================
  // DISCOVERY PLAYLIST
  // =========================================================================

  it('should generate discovery playlist', () => {
    const playlist = QueueRecommender.getDiscoveryPlaylist(mockTracks, 10);

    expect(playlist.length).toBeGreaterThan(0);
    expect(playlist.length).toBeLessThanOrEqual(10);
  });

  it('should have artist diversity in discovery playlist', () => {
    const playlist = QueueRecommender.getDiscoveryPlaylist(mockTracks, 10);
    const artists = new Set(playlist.map((t) => t.artist));

    expect(artists.size).toBeGreaterThan(1);
  });

  it('should limit tracks per artist', () => {
    const playlist = QueueRecommender.getDiscoveryPlaylist(mockTracks, 20);
    const artistCounts = new Map<string, number>();

    for (const track of playlist) {
      artistCounts.set(track.artist, (artistCounts.get(track.artist) || 0) + 1);
    }

    // Should have max 3 tracks per artist
    expect(Math.max(...artistCounts.values())).toBeLessThanOrEqual(3);
  });

  it('should handle empty tracks', () => {
    const playlist = QueueRecommender.getDiscoveryPlaylist([], 10);

    expect(playlist).toHaveLength(0);
  });

  // =========================================================================
  // EDGE CASES
  // =========================================================================

  it('should handle duplicate tracks', () => {
    const duplicates = [mockTracks[0], mockTracks[0], mockTracks[1]];
    const recommendations = QueueRecommender.recommendSimilarTracks(
      mockTracks[0],
      duplicates,
      5
    );

    expect(recommendations.every((r) => r.track.id !== mockTracks[0].id)).toBe(true);
  });

  it('should handle very similar durations', () => {
    const similar = [
      { ...mockTracks[0], id: 10, duration: 305 },
      { ...mockTracks[0], id: 11, duration: 302 },
    ];

    const result = QueueRecommender.calculateSimilarity(
      mockTracks[0],
      similar[0]
    );

    expect(result.factors.duration).toBeGreaterThan(0.9);
  });

  it('should handle very different durations', () => {
    const different = { ...mockTracks[0], id: 10, duration: 60 };

    const result = QueueRecommender.calculateSimilarity(
      mockTracks[0],
      different
    );

    expect(result.factors.duration).toBeLessThan(0.5);
  });

  // =========================================================================
  // PERFORMANCE
  // =========================================================================

  it('should handle large track libraries efficiently', () => {
    const largeTracks: Track[] = Array.from({ length: 5000 }, (_, i) => ({
      id: i,
      title: `Track ${i}`,
      artist: `Artist ${i % 100}`,
      album: `Album ${i % 50}`,
      duration: 200 + (i % 200),
      filepath: `/music/track${i}.mp3`,
    }));

    const startTime = performance.now();
    const recommendations = QueueRecommender.recommendForYou(
      largeTracks.slice(0, 50),
      largeTracks,
      10
    );
    const endTime = performance.now();

    expect(recommendations.length).toBeGreaterThan(0);
    expect(endTime - startTime).toBeLessThan(100); // Should be fast
  });
});
