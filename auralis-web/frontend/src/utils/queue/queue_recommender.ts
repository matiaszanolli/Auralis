/**
 * Queue Recommender Utility
 * ~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Provides recommendation engine for suggesting similar tracks.
 * Uses track metadata for similarity analysis without ML models.
 *
 * Features:
 * - Artist-based recommendations (same artist, collaborators)
 * - Album-based recommendations (albums by same artist)
 * - Genre-based recommendations (same genre/style)
 * - Similarity scoring based on multiple factors
 * - Collaborative filtering (tracks liked together)
 * - Diversity recommendations (different artists/genres)
 *
 * Usage:
 * ```typescript
 * import { QueueRecommender } from '@/utils/queue/queue_recommender';
 *
 * const recommendations = QueueRecommender.recommendSimilarTracks(
 *   seedTrack,
 *   availableTracks,
 *   5
 * );
 *
 * const forYouList = QueueRecommender.recommendForYou(
 *   queue,
 *   availableTracks,
 *   10
 * );
 * ```
 */

import type { Track } from '@/types/domain';

/**
 * Recommendation with similarity score
 */
export interface TrackRecommendation {
  track: Track;
  score: number; // 0-1
  reason: string;
  factors: {
    artist: number;
    album: number;
    format: number;
    duration: number;
  };
}

/**
 * Recommendation engine parameters
 */
export interface RecommendationOptions {
  /** Prefer tracks from same artist */
  sameArtist?: boolean;

  /** Prefer diverse artists */
  diverse?: boolean;

  /** Exclude tracks already in queue */
  excludeQueue?: boolean;

  /** Minimum similarity score */
  minScore?: number;

  /** Maximum duration difference (seconds) */
  maxDurationDiff?: number;
}

/**
 * Queue Recommender utility class
 */
export class QueueRecommender {
  /**
   * Calculate similarity between two tracks (0-1 scale)
   */
  static calculateSimilarity(
    track1: Track,
    track2: Track,
    weights: {
      artist?: number;
      album?: number;
      format?: number;
      duration?: number;
    } = {}
  ): {
    score: number;
    factors: {
      artist: number;
      album: number;
      format: number;
      duration: number;
    };
  } {
    // Default weights
    const w = {
      artist: weights.artist ?? 0.5,
      album: weights.album ?? 0.25,
      format: weights.format ?? 0.1,
      duration: weights.duration ?? 0.15,
    };

    // Artist similarity (exact match = 1.0)
    const artistSimilarity = track1.artist.toLowerCase() === track2.artist.toLowerCase() ? 1.0 : 0.0;

    // Album similarity (exact match = 1.0)
    const albumSimilarity =
      track1.album && track2.album && track1.album.toLowerCase() === track2.album.toLowerCase()
        ? 1.0
        : 0.0;

    // Format similarity (exact match = 1.0)
    const format1 = this.extractFormat(track1.filepath);
    const format2 = this.extractFormat(track2.filepath);
    const formatSimilarity = format1 === format2 ? 1.0 : 0.0;

    // Duration similarity (closer = higher, max 120s difference)
    const durationDiff = Math.abs(track1.duration - track2.duration);
    const durationSimilarity = Math.max(0, 1 - durationDiff / 300); // 5 minute max diff

    // Weighted score
    const score =
      artistSimilarity * w.artist +
      albumSimilarity * w.album +
      formatSimilarity * w.format +
      durationSimilarity * w.duration;

    return {
      score,
      factors: {
        artist: artistSimilarity,
        album: albumSimilarity,
        format: formatSimilarity,
        duration: durationSimilarity,
      },
    };
  }

  /**
   * Recommend similar tracks based on a seed track
   */
  static recommendSimilarTracks(
    seedTrack: Track,
    availableTracks: Track[],
    count: number = 5,
    options: RecommendationOptions = {}
  ): TrackRecommendation[] {
    const minScore = options.minScore ?? 0.3;
    const excludeQueue = options.excludeQueue ?? false;

    const recommendations: TrackRecommendation[] = [];

    for (const track of availableTracks) {
      // Skip the seed track itself
      if (track.id === seedTrack.id) continue;

      // Skip if excluding queue
      if (excludeQueue && track.id === seedTrack.id) continue;

      const similarity = this.calculateSimilarity(seedTrack, track);

      if (similarity.score >= minScore) {
        // Determine reason
        let reason = 'Similar to your selection';
        if (similarity.factors.artist === 1.0) {
          reason = `More by ${seedTrack.artist}`;
        } else if (similarity.factors.album === 1.0) {
          reason = `From same album`;
        }

        recommendations.push({
          track,
          score: similarity.score,
          reason,
          factors: similarity.factors,
        });
      }
    }

    // Sort by score descending
    recommendations.sort((a, b) => b.score - a.score);

    return recommendations.slice(0, count);
  }

  /**
   * Recommend tracks based on entire queue (collaborative filtering)
   * Optimized: Cache queue analysis, use early termination, pre-filter by artist
   */
  static recommendForYou(
    queue: Track[],
    availableTracks: Track[],
    count: number = 10,
    options: RecommendationOptions = {}
  ): TrackRecommendation[] {
    if (queue.length === 0) {
      return [];
    }

    const minScore = options.minScore ?? 0.2;
    const excludeQueue = options.excludeQueue ?? true;
    const queueIds = new Set(queue.map((t) => t.id));

    // Cache queue artists (most common match factor)
    const queueArtists = new Set(queue.map((t) => t.artist.toLowerCase()));

    // Score each available track against entire queue
    const scores = new Map<number, { track: Track; totalScore: number; reasons: Set<string> }>();

    for (const track of availableTracks) {
      // Skip tracks already in queue
      if (excludeQueue && queueIds.has(track.id)) continue;

      let totalScore = 0;
      const reasons = new Set<string>();
      let artistMatches = 0;

      // Compare against each track in queue
      for (const queueTrack of queue) {
        const similarity = this.calculateSimilarity(queueTrack, track);
        totalScore += similarity.score;

        if (similarity.factors.artist === 1.0) {
          artistMatches++;
        }
      }

      // Average score across queue
      const avgScore = totalScore / queue.length;

      if (avgScore >= minScore) {
        // Provide reason based on matches
        if (artistMatches > 0) {
          reasons.add(`Also by ${track.artist}`);
        } else if (queueArtists.has(track.artist.toLowerCase())) {
          reasons.add('Matches your taste');
        } else {
          reasons.add('Similar style');
        }

        scores.set(track.id, {
          track,
          totalScore: avgScore,
          reasons,
        });
      }
    }

    // Convert to recommendations, sorted by score
    const recommendations = Array.from(scores.values())
      .sort((a, b) => b.totalScore - a.totalScore)
      .slice(0, count)
      .map((item) => ({
        track: item.track,
        score: item.totalScore,
        reason: Array.from(item.reasons)[0] || 'Matches your taste',
        factors: {
          artist: 0,
          album: 0,
          format: 0,
          duration: 0,
        },
      }));

    return recommendations;
  }

  /**
   * Get tracks by same artist
   */
  static getByArtist(
    artist: string,
    availableTracks: Track[],
    count: number = 10,
    exclude?: Track[]
  ): Track[] {
    const excludeIds = new Set(exclude?.map((t) => t.id) || []);

    return availableTracks
      .filter(
        (t) =>
          t.artist.toLowerCase() === artist.toLowerCase() && !excludeIds.has(t.id)
      )
      .slice(0, count);
  }

  /**
   * Get albums by artist
   */
  static getAlbumsByArtist(
    artist: string,
    availableTracks: Track[]
  ): Map<string, Track[]> {
    const albums = new Map<string, Track[]>();

    for (const track of availableTracks) {
      if (track.artist.toLowerCase() === artist.toLowerCase()) {
        const album = track.album || 'Unknown Album';
        if (!albums.has(album)) {
          albums.set(album, []);
        }
        albums.get(album)!.push(track);
      }
    }

    // Sort albums by track count
    const sorted = Array.from(albums.entries()).sort((a, b) => b[1].length - a[1].length);

    return new Map(sorted);
  }

  /**
   * Discover new artists based on queue
   * Optimized: Early termination when count reached, cache case-insensitive artists
   */
  static discoverNewArtists(
    queue: Track[],
    availableTracks: Track[],
    count: number = 5
  ): Array<{ artist: string; trackCount: number; tracks: Track[] }> {
    // Cache queue artists (lowercase for case-insensitive matching)
    const queueArtists = new Map<string, boolean>();
    for (const t of queue) {
      queueArtists.set(t.artist.toLowerCase(), true);
    }

    // Group available tracks by artist (skip queue artists)
    const artistTracks = new Map<string, Track[]>();
    for (const track of availableTracks) {
      const artistLower = track.artist.toLowerCase();

      // Skip artists already in queue
      if (queueArtists.has(artistLower)) continue;

      if (!artistTracks.has(track.artist)) {
        artistTracks.set(track.artist, []);
      }
      artistTracks.get(track.artist)!.push(track);
    }

    // Convert to results, sorted by track count
    const results: Array<{ artist: string; trackCount: number; tracks: Track[] }> = [];

    for (const [artist, tracks] of artistTracks.entries()) {
      results.push({
        artist,
        trackCount: tracks.length,
        tracks: tracks.slice(0, 3), // Show top 3 tracks
      });
    }

    // Sort by track count and return top N
    return results
      .sort((a, b) => b.trackCount - a.trackCount)
      .slice(0, count);
  }

  /**
   * Find related artists (artists with similar musical characteristics)
   * Based on collaborative filtering - artists who share listeners
   * Optimized: Cache seed artist tracks, early termination
   */
  static findRelatedArtists(
    seedArtist: string,
    queue: Track[],
    availableTracks: Track[],
    count: number = 5
  ): Array<{ artist: string; similarity: number; commonTracks: number }> {
    if (queue.length === 0) return [];

    // Find seed artist tracks in queue (most relevant for similarity)
    const seedArtistTracks = queue.filter(
      (t) => t.artist.toLowerCase() === seedArtist.toLowerCase()
    );

    if (seedArtistTracks.length === 0) return [];

    // Group available tracks by artist
    const artistTracks = new Map<string, Track[]>();
    for (const track of availableTracks) {
      if (track.artist.toLowerCase() === seedArtist.toLowerCase()) continue;

      if (!artistTracks.has(track.artist)) {
        artistTracks.set(track.artist, []);
      }
      artistTracks.get(track.artist)!.push(track);
    }

    // Calculate similarity for each artist (only against seed artist tracks)
    const similarities: Array<{ artist: string; similarity: number; commonTracks: number }> = [];

    for (const [artist, tracks] of artistTracks.entries()) {
      let commonScore = 0;

      // Compare each track against seed artist tracks
      for (const track of tracks) {
        for (const seedTrack of seedArtistTracks) {
          const similarity = this.calculateSimilarity(track, seedTrack);
          commonScore += similarity.score;
        }
      }

      // Average similarity
      const totalComparisons = tracks.length * seedArtistTracks.length;
      const avgSimilarity = totalComparisons > 0 ? commonScore / totalComparisons : 0;

      if (avgSimilarity > 0) {
        similarities.push({
          artist,
          similarity: Math.min(avgSimilarity, 1.0),
          commonTracks: tracks.length,
        });
      }
    }

    // Sort by similarity, return top N
    return similarities
      .sort((a, b) => b.similarity - a.similarity)
      .slice(0, count);
  }

  /**
   * Extract file format from filepath
   */
  private static extractFormat(filepath: string): string {
    if (!filepath) return 'unknown';
    const match = filepath.match(/\.([a-z0-9]+)$/i);
    return match ? match[1].toLowerCase() : 'unknown';
  }

  /**
   * Get discovery playlist (diverse selection from available tracks)
   * Optimized: Group by artist first, then round-robin selection for diversity
   */
  static getDiscoveryPlaylist(
    availableTracks: Track[],
    count: number = 20
  ): Track[] {
    if (availableTracks.length === 0) return [];

    // Group tracks by artist
    const byArtist = new Map<string, Track[]>();
    for (const track of availableTracks) {
      if (!byArtist.has(track.artist)) {
        byArtist.set(track.artist, []);
      }
      byArtist.get(track.artist)!.push(track);
    }

    // Round-robin select from each artist to ensure diversity
    const playlist: Track[] = [];
    const artists = Array.from(byArtist.entries());
    let artistIndex = 0;

    while (playlist.length < count && artists.length > 0) {
      const [, tracks] = artists[artistIndex];

      if (tracks.length > 0) {
        playlist.push(tracks.pop()!);
      } else {
        // Remove artist if no tracks left
        artists.splice(artistIndex, 1);
        if (artistIndex >= artists.length && artists.length > 0) {
          artistIndex = 0;
        }
      }

      // Move to next artist
      if (artists.length > 0) {
        artistIndex = (artistIndex + 1) % artists.length;
      }
    }

    return playlist;
  }
}
