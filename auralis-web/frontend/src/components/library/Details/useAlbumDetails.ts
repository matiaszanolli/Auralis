/**
 * useAlbumDetails Hook
 *
 * Manages album data fetching and state:
 * - Fetch album details from API
 * - Handle loading/error states
 * - Format album metadata
 * - Support for favorite toggling
 */

import { useState } from 'react';
import { transformTracks } from '@/api/transformers/trackTransformer';
import type { AlbumTracksResponse } from '@/api/transformers/types';
import { isAlbumTracksShape } from '@/api/responseGuards';
import type { DetailTrack } from '@/types/domain';
import { ApiErrorHandler } from '@/types/api';
import { ENDPOINTS } from '@/config/api';
import { get, post, del } from '@/utils/apiRequest';
import { useAbortableResource } from '@/hooks/shared/useAbortableResource';
import { useToast } from '@/components/shared/Toast';
import { UNKNOWN_ARTIST_LABEL } from '@/utils/unknownLabels';

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

/** One album with its tracks, from `/api/albums/{id}/tracks`. */
const fetchAlbum = async (albumId: number, signal: AbortSignal): Promise<Album> => {
  // #4643: through the shared get()/ApiErrorHandler transport instead of a raw fetch() that
  // collapsed every non-OK response into one status-less Error, so a 404 (stale album link,
  // recoverable) and a 500 (possibly transient) can be told apart by the UI.
  const data = await get<AlbumTracksResponse>(`/api/albums/${albumId}/tracks`, {
    signal,
    validate: isAlbumTracksShape,
  });

  // Per-track fields are snake_case on the wire (Track.to_dict()), with `artists: string[]`;
  // the canonical transformer maps them (#4568, #4571). The album-level fields below are
  // genuinely snake_case on this endpoint and correct as-is: do not "normalise" them.
  const tracks = transformTracks(data.tracks ?? []);
  return {
    id: data.album_id,
    title: data.album_title,
    artist: data.artist ?? UNKNOWN_ARTIST_LABEL,
    artist_name: data.artist ?? UNKNOWN_ARTIST_LABEL,
    year: data.year ?? undefined,
    // #5170: genre is derived server-side (the modal genre of the tracks; Album has no column).
    genre: data.genre ?? undefined,
    track_count: data.total_tracks,
    total_duration: tracks.reduce((sum, t) => sum + (t.duration || 0), 0),
    tracks,
  };
};

export const useAlbumDetails = (albumId: number) => {
  const [isFavorite, setIsFavorite] = useState(false);
  const [savingFavorite, setSavingFavorite] = useState(false);
  const { error: errorToast } = useToast();

  const { data: album, loading, error } = useAbortableResource<Album>(
    albumId,
    (signal) => fetchAlbum(albumId, signal),
    {
      label: 'album details',
      // #5118: seed the heart from the server rather than leaving it false; `favorite` is on the
      // wire for every track (#2851) and survives transformTracks.
      onLoaded: (loaded) => setIsFavorite(loaded.tracks?.[0]?.favorite ?? false),
    },
  );

  const toggleFavorite = async () => {
    setSavingFavorite(true);
    try {
      // Use first track's ID to toggle favorite (albums don't have direct favorite endpoints)
      const trackId = album?.tracks?.[0]?.id;
      if (!trackId) {
        // #5647: a mutation failure must not touch the load `error` — that
        // state drives the full-page "Error Loading Album" branch in
        // AlbumDetailView, so a failed heart click used to blank the album
        // already on screen. Favorite problems surface as a toast instead.
        errorToast('Cannot favorite album: no tracks available');
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
      errorToast(ApiErrorHandler.parse(err).message);
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
  };
};
