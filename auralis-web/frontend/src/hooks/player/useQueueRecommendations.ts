/**
 * useQueueRecommendations Hook
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Provides track recommendations based on queue.
 * Suggests similar tracks, discovers new artists, and generates playlists.
 *
 * Usage:
 * ```typescript
 * const {
 *   forYouRecommendations,
 *   similarToCurrentTrack,
 *   discoveryPlaylist,
 *   newArtists,
 *   relatedArtists
 * } = useQueueRecommendations(queue, currentTrack, availableTracks);
 * ```
 *
 * Features:
 * - For You recommendations (collaborative filtering)
 * - Similar to current track
 * - Artist-based recommendations
 * - New artist discovery
 * - Related artist suggestions
 * - Discovery playlist generation
 * - Configurable similarity threshold
 *
 * @module hooks/player/useQueueRecommendations
 */

import { useMemo } from 'react';
import { QueueRecommender, type TrackRecommendation } from '@/utils/queue/queue_recommender';
import type { Track } from '@/types/domain';

/**
 * Discovery artist with sample tracks
 */
export interface DiscoveryArtist {
  artist: string;
  trackCount: number;
  tracks: Track[];
}

/**
 * Related artist with similarity score
 */
export interface RelatedArtist {
  artist: string;
  similarity: number; // 0-1
  commonTracks: number;
}

/**
 * Return type for useQueueRecommendations hook
 */
export interface QueueRecommendationsActions {
  /** Recommendations based on entire queue (For You) */
  forYouRecommendations: TrackRecommendation[];

  /** Recommendations similar to current track */
  similarToCurrentTrack: TrackRecommendation[];

  /** Discovery playlist (diverse selection) */
  discoveryPlaylist: Track[];

  /** New artists to explore */
  newArtists: DiscoveryArtist[];

  /** Artists related to current artist */
  relatedArtists: RelatedArtist[];

  /** Get recommendations for specific track */
  getRecommendationsFor: (track: Track, count?: number) => TrackRecommendation[];

  /** Get recommendations by artist */
  getByArtist: (artist: string, count?: number) => Track[];

  /** Get albums by artist */
  getAlbumsByArtist: (artist: string) => Map<string, Track[]>;

  /** Whether enough data for recommendations */
  hasEnoughData: boolean;
}

/**
 * Hook for getting queue recommendations
 *
 * @param queue Current queue tracks
 * @param currentTrack Currently playing track (if any)
 * @param availableTracks All available tracks to recommend from
 * @returns Recommendations and utility functions
 *
 * @example
 * ```typescript
 * const { queue, currentTrack } = usePlaybackQueue();
 * const { library } = useLibrary();
 *
 * const {
 *   forYouRecommendations,
 *   similarToCurrentTrack,
 *   newArtists
 * } = useQueueRecommendations(queue, currentTrack, library);
 *
 * // Show "For You" section
 * forYouRecommendations.slice(0, 5).map(rec => rec.track.title)
 * ```
 */
export function useQueueRecommendations(
  queue: Track[],
  currentTrack: Track | null,
  availableTracks: Track[]
): QueueRecommendationsActions {
  // Check if we have enough data
  const hasEnoughData = queue.length >= 3 && availableTracks.length > queue.length;

  // For You recommendations (based on entire queue)
  const forYouRecommendations = useMemo(() => {
    if (!hasEnoughData) return [];

    return QueueRecommender.recommendForYou(
      queue,
      availableTracks,
      10,
      {
        excludeQueue: true,
        minScore: 0.2,
      }
    );
  }, [queue, availableTracks, hasEnoughData]);

  // Similar to current track
  const similarToCurrentTrack = useMemo(() => {
    if (!currentTrack || availableTracks.length === 0) return [];

    return QueueRecommender.recommendSimilarTracks(
      currentTrack,
      availableTracks,
      8,
      {
        excludeQueue: true,
        minScore: 0.25,
      }
    );
  }, [currentTrack, availableTracks]);

  // Discovery playlist
  const discoveryPlaylist = useMemo(() => {
    if (availableTracks.length === 0) return [];

    return QueueRecommender.getDiscoveryPlaylist(availableTracks, 20);
  }, [availableTracks]);

  // New artists to discover
  const newArtists = useMemo(() => {
    if (queue.length === 0 || availableTracks.length === 0) return [];

    return QueueRecommender.discoverNewArtists(queue, availableTracks, 5);
  }, [queue, availableTracks]);

  // Related artists to current playing
  const relatedArtists = useMemo(() => {
    if (!currentTrack || availableTracks.length === 0) return [];

    return QueueRecommender.findRelatedArtists(
      currentTrack.artist,
      queue,
      availableTracks,
      5
    );
  }, [currentTrack, queue, availableTracks]);

  // Utility: Get recommendations for specific track
  const getRecommendationsFor = (track: Track, count: number = 5) => {
    return QueueRecommender.recommendSimilarTracks(
      track,
      availableTracks,
      count,
      {
        excludeQueue: true,
      }
    );
  };

  // Utility: Get tracks by artist
  const getByArtist = (artist: string, count: number = 10) => {
    return QueueRecommender.getByArtist(artist, availableTracks, count, queue);
  };

  // Utility: Get albums by artist
  const getAlbumsByArtist = (artist: string) => {
    return QueueRecommender.getAlbumsByArtist(artist, availableTracks);
  };

  return {
    forYouRecommendations,
    similarToCurrentTrack,
    discoveryPlaylist,
    newArtists,
    relatedArtists,
    getRecommendationsFor,
    getByArtist,
    getAlbumsByArtist,
    hasEnoughData,
  };
}
