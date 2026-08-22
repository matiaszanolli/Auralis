/**
 * useTrackFingerprint Hook
 * ~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Fetches fingerprint for a specific track.
 * Used by AlbumCharacterPane to show currently playing track's sonic character.
 *
 * Features:
 * - Lazy loading (only fetches when trackId is provided)
 * - Caching via React Query
 * - Error handling with graceful fallback
 * - Auto-polling when fingerprint not ready
 */

import { useQuery } from '@tanstack/react-query';
import type { AudioFingerprint } from '@/utils/fingerprintToGradient';
import { httpErrorFromResponse } from '@/utils/httpError';
import { getApiUrl } from '@/config/api';

interface TrackFingerprintResponse {
  track_id: number;
  track_title: string;
  artist: string;
  album: string;
  fingerprint: AudioFingerprint;
}

/**
 * Fetch track fingerprint from backend.
 *
 * A 404 is the one expected non-error outcome (fingerprint queued but not
 * ready yet), so it resolves to `null`. Everything else — a non-2xx status
 * or a network-level failure — rejects instead of being swallowed to `null`
 * (#4847): a 404 and "the endpoint is broken" used to be indistinguishable,
 * both driving refetchInterval's indefinite 5s poll and leaving
 * `query.error` permanently empty.
 */
const fetchTrackFingerprint = async (trackId: number): Promise<TrackFingerprintResponse | null> => {
  const response = await fetch(getApiUrl(`/api/tracks/${trackId}/fingerprint`));

  if (!response.ok) {
    // Track doesn't have fingerprint yet (queued for generation)
    if (response.status === 404) {
      return null;
    }
    // Surface the backend's `detail` and status rather than a bare
    // `statusText`, which is empty over HTTP/2 (#4626).
    throw await httpErrorFromResponse(response);
  }

  return await response.json();
};

/**
 * Hook to fetch track fingerprint with caching
 *
 * @param trackId - Track ID (null/undefined to skip fetching)
 * @param options - Query options
 * @returns Fingerprint data and metadata or null if unavailable
 *
 * @example
 * ```tsx
 * const { fingerprint, trackTitle, isLoading } = useTrackFingerprint(currentTrackId);
 *
 * <AlbumCharacterPane
 *   fingerprint={fingerprint}
 *   albumTitle={trackTitle}
 *   isLoading={isLoading}
 * />
 * ```
 */
export function useTrackFingerprint(
  trackId: number | null | undefined,
  options?: {
    enabled?: boolean;
    /** Retry interval in ms when fingerprint not ready (default: 5000) */
    retryInterval?: number;
  }
) {
  const enabled = (options?.enabled ?? true) && trackId != null && trackId > 0;
  const retryInterval = options?.retryInterval ?? 5000;

  const query = useQuery({
    queryKey: ['track-fingerprint', trackId],
    queryFn: () => trackId ? fetchTrackFingerprint(trackId) : null,
    staleTime: 5 * 60 * 1000, // 5 minutes (fingerprints don't change)
    gcTime: 30 * 60 * 1000,   // 30 minutes cache retention
    enabled,
    retry: false, // Don't retry on 404
    // Re-fetch periodically if fingerprint not ready (queued for generation)
    refetchInterval: (query) => {
      // #4847: a failed fetch (5xx, network error) leaves `data` at its
      // last value — which is `null` for a track that was still queued
      // when it started failing — so the error check must come first, or
      // polling never stops and the error is silently masked as "pending"
      // forever.
      if (query.state.status === 'error') {
        return false;
      }
      // If we got null (not ready), poll every 5 seconds
      if (query.state.data === null) {
        return retryInterval;
      }
      return false; // Stop polling once we have data
    },
  });

  const data = query.data;

  return {
    fingerprint: data?.fingerprint ?? null,
    trackTitle: data?.track_title ?? null,
    artist: data?.artist ?? null,
    album: data?.album ?? null,
    isLoading: query.isLoading,
    // Fingerprint queued but not ready — distinct from a genuine error
    // (#4847), which used to look identical to this state.
    isPending: query.data === null && !query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}