/**
 * useAlbumDetails Hook
 *
 * Manages album data fetching and state:
 * - Fetch album details from API
 * - Handle loading/error states
 * - Format album metadata
 * - Support for favorite toggling
 */

import { useState, useEffect } from 'react';
import { transformTracks } from '@/api/transformers/trackTransformer';
import type { TrackApiResponse } from '@/api/transformers/types';
import type { DetailTrack } from '@/types/domain';
import type { ApiError } from '@/types/api';
import { ApiErrorHandler } from '@/types/api';
import { ENDPOINTS } from '@/config/api';
import { get, post, del } from '@/utils/apiRequest';
import { isAbortError } from '@/utils/errorGuards';

export interface Album {
  id: number;
  title: string;
  artist: string;
  artist_name?: string;
  year?: number;
  genre?: string;
  track_count: number;
  total_duration: number;
  tracks?: DetailTrack[];
}

export const useAlbumDetails = (albumId: number) => {
  const [album, setAlbum] = useState<Album | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [isFavorite, setIsFavorite] = useState(false);
  const [savingFavorite, setSavingFavorite] = useState(false);

  // #3601: AbortController on the fetch so we don't setState on a dead
  // component if the user navigates away mid-request, and so the in-flight
  // request itself is cancelled rather than running to completion uselessly.
  useEffect(() => {
    const controller = new AbortController();
    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        // #4643: routed through the shared get()/ApiErrorHandler transport
        // (like the rest of the library hooks) instead of a raw fetch() that
        // collapsed every non-OK response into an identical, status-less
        // Error — a 404 (stale/deleted album link, recoverable) and a 500
        // (possibly transient) rendered the same, with no way for the UI to
        // offer a differentiated recovery action.
        const data = await get<any>(`/api/albums/${albumId}/tracks`, {
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;

        // `/api/albums/{id}/tracks` serialises per-track fields in snake_case
        // (serialize_tracks → Track.to_dict()), so the previous inline mapper —
        // which read t.artworkUrl / t.trackNumber / t.discNumber / t.albumId —
        // produced null for every one of them, and blank artists (the wire key
        // is `artists: string[]`). The `(t: DetailTrack)` annotation asserted the
        // camelCase shape onto raw JSON, so TypeScript endorsed the wrong keys.
        // Routed through the canonical transformer instead (#4568, #4571).
        //
        // NOTE: the album-level fields below are genuinely snake_case on this
        // endpoint and are correct as-is — do not "normalise" them.
        const tracks = transformTracks(
          (data.tracks ?? []) as TrackApiResponse[]
        ) as DetailTrack[];

        const albumData: Album = {
          id: data.album_id,
          title: data.album_title,
          artist: data.artist,
          artist_name: data.artist,
          year: data.year,
          // #5170: genre is derived server-side (modal genre across the
          // album's tracks — Album has no genre column). Without this line
          // AlbumMetadata's "Genre:" row was unreachable.
          genre: data.genre,
          track_count: data.total_tracks,
          total_duration: tracks.reduce((sum, t) => sum + (t.duration || 0), 0),
          tracks,
        };
        setAlbum(albumData);
        // #5118: seed the heart from the server rather than leaving it false.
        // `favorite` is on the wire for every track (DEFAULT_TRACK_FIELDS, #2851)
        // and survives transformTracks, so the control no longer misrepresents
        // stored state before the first click.
        setIsFavorite(tracks[0]?.favorite ?? false);
      } catch (err) {
        // #4643: get() wraps even a caller-triggered abort into an
        // APIRequestError rather than preserving the original AbortError's
        // `.name` (apiRequest.ts's own catch-all does this deliberately —
        // see its tests), so isAbortError(err) alone would miss it. The
        // signal is authoritative regardless of how the shared transport
        // happens to shape an abort; check it first.
        if (controller.signal.aborted || isAbortError(err)) return;
        console.error('Error fetching album details:', err);
        setError(ApiErrorHandler.parse(err));
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    };
    run();
    return () => controller.abort();
  }, [albumId]);

  const toggleFavorite = async () => {
    setSavingFavorite(true);
    try {
      // Use first track's ID to toggle favorite (albums don't have direct favorite endpoints)
      const trackId = album?.tracks?.[0]?.id;
      if (!trackId) {
        setError({ status: 400, message: 'Cannot favorite album: no tracks available' });
        return;
      }

      // #5118: the backend has no toggle semantic — POST sets favorite=true and
      // DELETE sets it false, each unconditionally. Always POSTing meant
      // un-favoriting never reached the server while the UI reported success.
      // #4643: routed through the shared transport, same as the fetch above.
      const result = isFavorite
        ? await del<{ favorite?: boolean }>(ENDPOINTS.TRACK_FAVORITE(trackId))
        : await post<{ favorite?: boolean }>(ENDPOINTS.TRACK_FAVORITE(trackId));

      // Take the new state from the server's `favorite` field rather than
      // negating the local one, so the control cannot drift from stored state.
      setIsFavorite(
        typeof result?.favorite === 'boolean' ? result.favorite : !isFavorite
      );
    } catch (err) {
      console.error('Error toggling favorite:', err);
      setError(ApiErrorHandler.parse(err));
    } finally {
      setSavingFavorite(false);
    }
  };

  return {
    album,
    loading,
    error,
    isFavorite,
    savingFavorite,
    toggleFavorite,
    setError,
  };
};
