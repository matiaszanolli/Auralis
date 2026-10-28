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
import { getArtistTracks, type TrackInArtist } from '@/services/libraryService';

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

/** The artist-tracks wire row as the DetailTrack the detail view renders and plays. */
const toDetailTrack = (track: TrackInArtist, artistName: string): DetailTrack => ({
  id: track.id,
  title: track.title,
  artist: artistName,
  album: track.album ?? '',
  albumId: track.album_id,
  duration: track.duration,
  trackNumber: track.track_number,
  discNumber: track.disc_number,
});

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
        // The detail response carries albums and counts only; the tracks come from
        // their own endpoint, so "All Tracks" and Play All / Shuffle had nothing to
        // work with (#6009). Fetched together; a failed track list is not fatal.
        const [data, trackList] = await Promise.all([
          get<ArtistDetailApiResponse>(`/api/artists/${artistId}`, { signal: controller.signal }),
          getArtistTracks(artistId, controller.signal).catch((err) => {
            if (!controller.signal.aborted) console.error('Error fetching artist tracks:', err);
            return null;
          }),
        ]);
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
          tracks: (trackList?.tracks ?? []).map((t) => toDetailTrack(t, base.name)),
        };
        setArtist(artistData);
      } catch (err) {
        // get() rethrows a caller abort as the raw AbortError (#5653); the signal
        // also covers a request that failed some other way after being cancelled.
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
