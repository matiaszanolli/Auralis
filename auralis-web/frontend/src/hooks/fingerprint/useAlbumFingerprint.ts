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

interface AlbumFingerprintResponse {
  album_id: number;
  album_title: string;
  track_count: number;
  fingerprinted_track_count: number;
  fingerprint: AudioFingerprint;
}

/**
 * Fetch album fingerprint from backend
 */
const fetchAlbumFingerprint = async (albumId: number): Promise<AudioFingerprint | null> => {
  try {
    const response = await fetch(`/api/albums/${albumId}/fingerprint`);

    if (!response.ok) {
      // Album doesn't have fingerprints yet, return null (will use hash fallback)
      if (response.status === 404) {
        return null;
      }
      throw new Error(`Failed to fetch album fingerprint: ${response.statusText}`);
    }

    const data: AlbumFingerprintResponse = await response.json();
    return data.fingerprint;
  } catch (error) {
    console.warn(`Failed to fetch fingerprint for album ${albumId}:`, error);
    return null; // Graceful fallback to hash-based gradient
  }
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
    retry: false, // Don't retry on 404 (album simply doesn't have fingerprints)
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
export function useAlbumFingerprints(albumIds: number[]) {
  const queries = useQuery({
    queryKey: ['album-fingerprints-batch', albumIds.sort().join(',')],
    queryFn: async () => {
      // Fetch all fingerprints in parallel
      const results = await Promise.allSettled(
        albumIds.map(id => fetchAlbumFingerprint(id))
      );

      // Map results back to album IDs
      const fingerprintMap = new Map<number, AudioFingerprint | null>();
      results.forEach((result, index) => {
        const albumId = albumIds[index];
        if (result.status === 'fulfilled') {
          fingerprintMap.set(albumId, result.value);
        } else {
          fingerprintMap.set(albumId, null);
        }
      });

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
