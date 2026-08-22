/**
 * useAlbumFingerprint Hook
 * ~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Fetches median fingerprint for an album (aggregated from all tracks).
 * Used to generate unique gradient placeholders based on sonic identity.
 *
 * Features:
 * - Lazy loading (only fetches when needed)
 * - Caching via React Query
 * - Error handling with graceful fallback
 * - Returns partial fingerprint for safe gradient generation
 */

import { useQuery } from '@tanstack/react-query';
import type { AudioFingerprint } from '@/utils/fingerprintToGradient';
import { httpErrorFromResponse } from '@/utils/httpError';

interface AlbumFingerprintResponse {
  album_id: number;
  album_title: string;
  track_count: number;
  fingerprinted_track_count: number;
  fingerprint: AudioFingerprint;
}

/**
 * Fetch album fingerprint from backend.
 *
 * A 404 is the one expected non-error outcome (no fingerprint yet), so it
 * resolves to `null` and the caller falls back to the hash gradient. Everything
 * else — a non-2xx status or a network-level failure — rejects.
 *
 * This used to wrap its own `throw` in a `try/catch` that turned every failure
 * back into `null` (#5122), which made a broken endpoint indistinguishable from
 * "this album has no fingerprint yet": the `useQuery` queryFn never rejected, so
 * `query.error` was permanently `undefined` and `query.isError` permanently
 * `false`. It also disabled retries — React Query is configured `retry: 1`, and
 * a resolved `null` is a success, so a transient 500 was cached for the 5-minute
 * staleTime instead of being retried. #4847 fixed exactly this in the sibling
 * `useTrackFingerprint`; this is the half that sweep missed, and it converges on
 * that hook's shape rather than inventing a third.
 */
const fetchAlbumFingerprint = async (albumId: number): Promise<AudioFingerprint | null> => {
  const response = await fetch(`/api/albums/${albumId}/fingerprint`);

  if (!response.ok) {
    // Album doesn't have fingerprints yet, return null (will use hash fallback)
    if (response.status === 404) {
      return null;
    }
    // Surface the backend's `detail` and status rather than a bare
    // `statusText`, which is empty over HTTP/2 (#4626).
    throw await httpErrorFromResponse(response);
  }

  const data: AlbumFingerprintResponse = await response.json();
  return data.fingerprint;
};

/**
 * Hook to fetch album fingerprint with caching
 *
 * @param albumId - Album ID
 * @param options - Query options
 * @returns Fingerprint data or null if unavailable
 *
 * @example
 * ```tsx
 * const { fingerprint, isLoading } = useAlbumFingerprint(albumId);
 *
 * <AlbumCard
 *   albumId={albumId}
 *   fingerprint={fingerprint}
 *   ...
 * />
 * ```
 */
export function useAlbumFingerprint(
  albumId: number,
  options?: {
    enabled?: boolean;
  }
) {
  const query = useQuery({
    queryKey: ['album-fingerprint', albumId],
    queryFn: () => fetchAlbumFingerprint(albumId),
    staleTime: 5 * 60 * 1000, // 5 minutes (fingerprints don't change often)
    gcTime: 30 * 60 * 1000,   // 30 minutes cache retention
    enabled: options?.enabled ?? true,
    // Kept false, but the original rationale no longer applies: since #5122 a
    // 404 resolves to `null` rather than throwing, so it was never going to be
    // retried anyway. What `false` now suppresses is retrying a genuine 5xx.
    // Left as-is deliberately — album art is decorative and every tile has a
    // hash-gradient fallback, so retrying a failing endpoint once per visible
    // album is not obviously worth the request volume. Revisit with #5122's
    // close comment if that trade changes.
    retry: false,
  });

  return {
    fingerprint: query.data ?? undefined,
    isLoading: query.isLoading,
    error: query.error,
  };
}

/**
 * Batch fetch multiple album fingerprints
 * More efficient than individual queries when rendering many albums
 *
 * Note: This is a simplified version. For production, consider implementing
 * a batch endpoint like GET /api/albums/fingerprints?ids=1,2,3
 */
/**
 * #3644: chunk-based concurrency cap. The Electron-local FastAPI serves
 * all requests serially in the ASGI loop, so firing 200 requests at once
 * starves audio-streaming requests of I/O time. Resolve in groups of N
 * sequentially; within each group requests still fan out.
 */
const FINGERPRINT_BATCH_CONCURRENCY = 10;

export function useAlbumFingerprints(albumIds: number[]) {
  const queries = useQuery({
    queryKey: ['album-fingerprints-batch', [...albumIds].sort().join(',')],
    queryFn: async () => {
      const fingerprintMap = new Map<number, AudioFingerprint | null>();

      for (let i = 0; i < albumIds.length; i += FINGERPRINT_BATCH_CONCURRENCY) {
        const chunk = albumIds.slice(i, i + FINGERPRINT_BATCH_CONCURRENCY);
        const results = await Promise.allSettled(
          chunk.map(id => fetchAlbumFingerprint(id))
        );
        results.forEach((result, index) => {
          const albumId = chunk[index];
          if (result.status === 'rejected') {
            // Per-album tolerance is correct HERE and only here: one bad album
            // must not empty a whole grid, and every tile has a hash gradient to
            // fall back on. Before #5122 this branch was dead code, because
            // fetchAlbumFingerprint caught its own errors and always fulfilled.
            console.warn(`Failed to fetch fingerprint for album ${albumId}:`, result.reason);
          }
          fingerprintMap.set(
            albumId,
            result.status === 'fulfilled' ? result.value : null
          );
        });
      }

      return fingerprintMap;
    },
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
    enabled: albumIds.length > 0,
  });

  return {
    fingerprints: queries.data ?? new Map(),
    isLoading: queries.isLoading,
    error: queries.error,
  };
}
