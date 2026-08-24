/**
 * useArtistDetailsData Hook
 *
 * Manages artist data fetching and state
 */

import { useState, useEffect } from 'react';
import type { Artist as DomainArtist, DetailTrack } from '@/types/domain';
import type { ArtistDetailApiResponse } from '@/api/transformers/types';
import type { ApiError } from '@/types/api';
import { ApiErrorHandler } from '@/types/api';
import { transformArtistDetail } from '@/api/transformers/artistTransformer';
import { isAbortError } from '@/utils/errorGuards';
import { get } from '@/utils/apiRequest';

export interface Album {
  id: number;
  title: string;
  year?: number;
  track_count: number;
  total_duration: number;
}

export interface Artist extends DomainArtist {
  albums?: Album[];
  tracks?: DetailTrack[];
}

export const useArtistDetailsData = (artistId: number) => {
  const [artist, setArtist] = useState<Artist | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);

  // #3601: AbortController on the fetch to prevent setState on dead component
  // and to cancel the in-flight request when the user navigates away.
  useEffect(() => {
    const controller = new AbortController();
    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        // #4643: routed through the shared get()/ApiErrorHandler transport,
        // same fix and same rationale as the sibling useAlbumDetails.ts — a
        // raw fetch() collapsed a 404 and a 500 into an identical, status-less
        // Error with no way for the UI to offer a differentiated recovery
        // action.
        const data = await get<ArtistDetailApiResponse>(`/api/artists/${artistId}`, {
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;

        const base = transformArtistDetail(data);
        const artistData: Artist = {
          ...base,
          albums: (data.albums || []).map((a) => ({
            id: a.id,
            title: a.title,
            year: a.year ?? undefined,
            track_count: a.track_count,
            total_duration: a.total_duration ?? 0,
          })),
          tracks: [],
        };
        setArtist(artistData);
      } catch (err) {
        // #4643: get() wraps even a caller-triggered abort into an
        // APIRequestError rather than preserving the original AbortError's
        // `.name` — see useAlbumDetails.ts for the full rationale. Check the
        // signal first; it is authoritative regardless of how the shared
        // transport happens to shape an abort.
        if (controller.signal.aborted || isAbortError(err)) return;
        console.error('Error fetching artist details:', err);
        setError(ApiErrorHandler.parse(err));
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    };
    run();
    return () => controller.abort();
  }, [artistId]);

  return {
    artist,
    loading,
    error,
  };
};
