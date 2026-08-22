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

import { useState, useCallback, useEffect, useRef } from 'react';
import { isAbortError } from '@/utils/errorGuards';
import { httpErrorFromResponse, type HttpStatusError } from '@/utils/httpError';
import { getApiUrl } from '@/config/api';
// LRU + TTL cache, keyed on every parameter that reaches the wire (#4629).
import {
  getCacheKey,
  readSimilarityCache,
  writeSimilarityCache,
} from './similarityCache';

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
  /** Error message (if search failed) — the backend's `detail` when it sent one */
  error: string | null;
  /**
   * HTTP status of the failed request, or null when the failure had none
   * (network error) or nothing has failed.
   *
   * Callers need this to tell apart three states the backend deliberately
   * distinguishes but which all look like "an error" without it (#4626):
   * a 404 whose detail says the track was queued for fingerprinting (transient,
   * retry shortly), a 503 (similarity system still initialising, also
   * transient), and a genuine 404 for a track that does not exist.
   */
  errorStatus: number | null;
  /** Find similar tracks for a given track ID */
  findSimilar: (trackId: number, options?: SimilarityOptions) => Promise<SimilarTrack[]>;
  /** Clear current results */
  clear: () => void;
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
  const [errorStatus, setErrorStatus] = useState<number | null>(null);

  // Track current request to prevent race conditions
  const currentRequestRef = useRef<number | null>(null);

  // #3616/#3646: abort in-flight similarity fetches when the modal closes or
  // the user changes track. Previously the request continued to completion
  // and only the setState was guarded.
  const abortRef = useRef<AbortController | null>(null);

  // Abort any in-flight similarity fetch on unmount so dismissing the modal
  // mid-search doesn't leave the backend running or loading stuck (#4162).
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      abortRef.current = null;
    };
  }, []);

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

      // Check cache first. `useGraph` is part of the key: it selects between
      // two different backend data sources, so omitting it aliased the two
      // answers onto one entry (#4629).
      const cacheKey = getCacheKey(trackId, limit, includeDetails, useGraph);
      const cached = readSimilarityCache(cacheKey);
      if (cached) {
        setSimilarTracks(cached);
        setLoading(false);
        setError(null);
        return cached;
      }

      // Start search
      setLoading(true);
      setError(null);
      setErrorStatus(null);

      // Cancel any previous in-flight request before starting a new one.
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        // Build query parameters
        const params = new URLSearchParams({
          limit: limit.toString(),
          use_graph: useGraph.toString(),
          include_details: includeDetails.toString(),
        });

        // Call backend API
        const response = await fetch(
          getApiUrl(`/api/similarity/tracks/${trackId}/similar?${params.toString()}`),
          {
            method: 'GET',
            headers: {
              'Content-Type': 'application/json',
            },
            signal: controller.signal,
          }
        );

        if (!response.ok) {
          // Read the backend's `detail` before the body is discarded (#4626).
          // similarity.py encodes the actionable part of the failure there —
          // "Track N does not have a fingerprint. Queued for background
          // processing." is a different situation from "track not found", and
          // both arrive as a 404. `statusText` is empty over HTTP/2, so the old
          // message could degrade to "Similarity search failed: 404 ".
          throw await httpErrorFromResponse(response);
        }

        // Parse response (backend uses snake_case, convert to camelCase)
        const data = await response.json();
        interface RawSimilarTrack {
          track_id: number;
          distance: number;
          similarity_score: number;
          rank: number;
          title: string;
          artist: string;
          album: string;
        }

        const results: SimilarTrack[] = (data as RawSimilarTrack[]).map((item) => ({
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
          writeSimilarityCache(cacheKey, results);
          setLoading(false);
        }

        return results;
      } catch (err) {
        if (isAbortError(err)) {
          // Caller cancelled — no state to update, no error to surface.
          throw err;
        }
        // Check if this is still the current request
        if (currentRequestRef.current === trackId) {
          const message =
            err instanceof Error ? err.message : 'Failed to find similar tracks';
          console.error(`[useSimilarTracks] Error finding similar tracks:`, err);
          setError(message);
          setErrorStatus((err as HttpStatusError)?.status ?? null);
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
    abortRef.current?.abort();
    abortRef.current = null;
    setSimilarTracks(null);
    setError(null);
    setErrorStatus(null);
    setLoading(false);
    currentRequestRef.current = null;
  }, []);

  return {
    similarTracks,
    loading,
    error,
    errorStatus,
    findSimilar,
    clear,
  };
}

export default useSimilarTracks;
