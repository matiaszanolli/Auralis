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

interface TrackFingerprintResponse {
  track_id: number;
  track_title: string;
  artist: string;
  album: string;
  fingerprint: AudioFingerprint;
}

/**
 * Fetch track fingerprint from backend
 */
const fetchTrackFingerprint = async (trackId: number): Promise<TrackFingerprintResponse | null> => {
  try {
    const response = await fetch(`/api/tracks/${trackId}/fingerprint`);

    if (!response.ok) {
      // Track doesn't have fingerprint yet (queued for generation)
      if (response.status === 404) {
        return null;
      }
      throw new Error(`Failed to fetch track fingerprint: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.warn(`Failed to fetch fingerprint for track ${trackId}:`, error);
    return null; // Graceful fallback
  }
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
    isPending: query.data === null, // Fingerprint queued but not ready
    error: query.error,
    refetch: query.refetch,
  };
}

/**
 * Hook to get fingerprint for currently playing track
 * Automatically uses the current track from player state
 */
export function usePlayingTrackFingerprint() {
  // This would integrate with Redux player state
  // For now, it's a simple wrapper that can be enhanced later
  return useTrackFingerprint(null, { enabled: false });
}
