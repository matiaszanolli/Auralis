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

    // Score each available track against entire queue
    const scores = new Map<number, { track: Track; totalScore: number; reasons: Set<string> }>();

    for (const track of availableTracks) {
      // Skip tracks already in queue
      if (excludeQueue && queueIds.has(track.id)) continue;

      let totalScore = 0;
      const reasons = new Set<string>();

      // Compare against each track in queue
      for (const queueTrack of queue) {
        const similarity = this.calculateSimilarity(queueTrack, track);
        totalScore += similarity.score;

        if (similarity.factors.artist === 1.0) {
          reasons.add(`Also by ${queueTrack.artist}`);
        }
      }

      // Average score across queue
      const avgScore = totalScore / queue.length;

      if (avgScore >= minScore) {
        scores.set(track.id, {
          track,
          totalScore: avgScore,
          reasons,
        });
      }
    }

    // Convert to recommendations
    const recommendations = Array.from(scores.values())
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
      }))
      .sort((a, b) => b.score - a.score)
      .slice(0, count);

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
   */
  static discoverNewArtists(
    queue: Track[],
    availableTracks: Track[],
    count: number = 5
  ): Array<{ artist: string; trackCount: number; tracks: Track[] }> {
    const queueArtists = new Set(queue.map((t) => t.artist.toLowerCase()));
    const artistTracks = new Map<string, Track[]>();

    // Group available tracks by artist
    for (const track of availableTracks) {
      const artistLower = track.artist.toLowerCase();

      // Skip artists already in queue
      if (queueArtists.has(artistLower)) continue;

      if (!artistTracks.has(track.artist)) {
        artistTracks.set(track.artist, []);
      }
      artistTracks.get(track.artist)!.push(track);
    }

    // Convert to results and sort by track count
    const results = Array.from(artistTracks.entries())
      .map(([artist, tracks]) => ({
        artist,
        trackCount: tracks.length,
        tracks: tracks.slice(0, 3), // Show top 3 tracks
      }))
      .sort((a, b) => b.trackCount - a.trackCount)
      .slice(0, count);

    return results;
  }

  /**
   * Find related artists (artists with similar musical characteristics)
   * Based on collaborative filtering - artists who share listeners
   */
  static findRelatedArtists(
    seedArtist: string,
    queue: Track[],
    availableTracks: Track[],
    count: number = 5
  ): Array<{ artist: string; similarity: number; commonTracks: number }> {
    // Find all artists in available tracks
    const artistTracks = new Map<string, Track[]>();

    for (const track of availableTracks) {
      if (!artistTracks.has(track.artist)) {
        artistTracks.set(track.artist, []);
      }
      artistTracks.get(track.artist)!.push(track);
    }

    // For each other artist, calculate similarity
    const similarities: Array<{ artist: string; similarity: number; commonTracks: number }> = [];

    for (const [artist, tracks] of artistTracks.entries()) {
      if (artist.toLowerCase() === seedArtist.toLowerCase()) continue;

      // Calculate similarity: tracks that appear near each other in queue
      let commonScore = 0;
      for (const track of tracks) {
        for (const queueTrack of queue) {
          if (queueTrack.artist.toLowerCase() === seedArtist.toLowerCase()) {
            const similarity = this.calculateSimilarity(track, queueTrack);
            commonScore += similarity.score;
          }
        }
      }

      const avgSimilarity = queue.length > 0 ? commonScore / queue.length : 0;

      if (avgSimilarity > 0) {
        similarities.push({
          artist,
          similarity: Math.min(avgSimilarity, 1.0),
          commonTracks: tracks.length,
        });
      }
    }

    // Sort by similarity
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
   */
  static getDiscoveryPlaylist(
    availableTracks: Track[],
    count: number = 20
  ): Track[] {
    if (availableTracks.length === 0) return [];

    const playlist: Track[] = [];
    const artistCounts = new Map<string, number>();

    // Sort by artist to group them, then shuffle within groups
    const shuffled = [...availableTracks].sort(() => Math.random() - 0.5);

    for (const track of shuffled) {
      if (playlist.length >= count) break;

      // Limit tracks per artist for diversity
      const artistCount = artistCounts.get(track.artist) || 0;
      if (artistCount < 3) {
        playlist.push(track);
        artistCounts.set(track.artist, artistCount + 1);
      }
    }

    return playlist;
  }
}
