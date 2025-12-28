/**
 * useSimilarTracks Hook - Phase 5: Mood-Aware Interaction
 *
 * Hook for finding similar tracks using fingerprint-based similarity search.
 * Uses the backend `/api/similarity/tracks/{track_id}/similar` endpoint.
 *
 * Features:
 * - Async similarity search with loading/error states
 * - In-memory caching by track ID (prevents redundant API calls)
 * - Optional track metadata inclusion
 * - Configurable result limit (1-100 tracks)
 *
 * Usage:
 * ```tsx
 * const { similarTracks, loading, error, findSimilar } = useSimilarTracks();
 *
 * // Find similar tracks
 * await findSimilar(trackId, { limit: 10, includeDetails: true });
 *
 * // Display results
 * {similarTracks.map(track => (
 *   <SimilarTrackItem key={track.trackId} track={track} />
 * ))}
 * ```
 */

import { useState, useCallback, useRef } from 'react';

/**
 * Similar track response model (matches backend SimilarTrack)
 */
export interface SimilarTrack {
  /** ID of the similar track */
  trackId: number;
  /** Fingerprint distance (lower = more similar) */
  distance: number;
  /** Similarity score 0-1 (higher = more similar) */
  similarityScore: number;
  /** Rank in similarity (1=most similar) */
  rank?: number;
  /** Track title (if includeDetails=true) */
  title?: string;
  /** Track artist (if includeDetails=true) */
  artist?: string;
  /** Track album (if includeDetails=true) */
  album?: string;
}

/**
 * Similarity search options
 */
export interface SimilarityOptions {
  /** Number of similar tracks to return (1-100, default: 10) */
  limit?: number;
  /** Use pre-computed K-NN graph if available (default: true) */
  useGraph?: boolean;
  /** Include track metadata in response (default: true) */
  includeDetails?: boolean;
}

/**
 * Hook return type
 */
interface UseSimilarTracksReturn {
  /** List of similar tracks (null if not loaded) */
  similarTracks: SimilarTrack[] | null;
  /** Is similarity search in progress? */
  loading: boolean;
  /** Error message (if search failed) */
  error: string | null;
  /** Find similar tracks for a given track ID */
  findSimilar: (trackId: number, options?: SimilarityOptions) => Promise<SimilarTrack[]>;
  /** Clear current results */
  clear: () => void;
}

/**
 * In-memory cache for similarity results
 * Key: `${trackId}:${limit}:${includeDetails}`, Value: SimilarTrack[]
 */
const similarityCache = new Map<string, SimilarTrack[]>();

/**
 * Generate cache key from search parameters
 */
function getCacheKey(trackId: number, limit: number, includeDetails: boolean): string {
  return `${trackId}:${limit}:${includeDetails}`;
}

/**
 * useSimilarTracks Hook
 *
 * Finds similar tracks using fingerprint-based similarity search.
 * Caches results in memory to avoid redundant API calls.
 *
 * @returns Similar tracks state and search function
 */
export function useSimilarTracks(): UseSimilarTracksReturn {
  const [similarTracks, setSimilarTracks] = useState<SimilarTrack[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Track current request to prevent race conditions
  const currentRequestRef = useRef<number | null>(null);

  /**
   * Find similar tracks for a given track ID
   */
  const findSimilar = useCallback(
    async (
      trackId: number,
      options: SimilarityOptions = {}
    ): Promise<SimilarTrack[]> => {
      const {
        limit = 10,
        useGraph = true,
        includeDetails = true,
      } = options;

      // Validate limit
      if (limit < 1 || limit > 100) {
        throw new Error('Limit must be between 1 and 100');
      }

      currentRequestRef.current = trackId;

      // Check cache first
      const cacheKey = getCacheKey(trackId, limit, includeDetails);
      const cached = similarityCache.get(cacheKey);
      if (cached) {
        setSimilarTracks(cached);
        setLoading(false);
        setError(null);
        return cached;
      }

      // Start search
      setLoading(true);
      setError(null);

      try {
        // Build query parameters
        const params = new URLSearchParams({
          limit: limit.toString(),
          use_graph: useGraph.toString(),
          include_details: includeDetails.toString(),
        });

        // Call backend API
        const response = await fetch(
          `/api/similarity/tracks/${trackId}/similar?${params.toString()}`,
          {
            method: 'GET',
            headers: {
              'Content-Type': 'application/json',
            },
          }
        );

        if (!response.ok) {
          throw new Error(
            `Similarity search failed: ${response.status} ${response.statusText}`
          );
        }

        // Parse response (backend uses snake_case, convert to camelCase)
        const data = await response.json();
        const results: SimilarTrack[] = data.map((item: any) => ({
          trackId: item.track_id,
          distance: item.distance,
          similarityScore: item.similarity_score,
          rank: item.rank,
          title: item.title,
          artist: item.artist,
          album: item.album,
        }));

        // Check if this is still the current request (prevent race condition)
        if (currentRequestRef.current === trackId) {
          setSimilarTracks(results);
          similarityCache.set(cacheKey, results);
          setLoading(false);
        }

        return results;
      } catch (err) {
        // Check if this is still the current request
        if (currentRequestRef.current === trackId) {
          const message =
            err instanceof Error ? err.message : 'Failed to find similar tracks';
          console.error(`[useSimilarTracks] Error finding similar tracks:`, err);
          setError(message);
          setLoading(false);
        }

        throw err;
      }
    },
    []
  );

  /**
   * Clear current results
   */
  const clear = useCallback(() => {
    setSimilarTracks(null);
    setError(null);
    setLoading(false);
    currentRequestRef.current = null;
  }, []);

  return {
    similarTracks,
    loading,
    error,
    findSimilar,
    clear,
  };
}

export default useSimilarTracks;
