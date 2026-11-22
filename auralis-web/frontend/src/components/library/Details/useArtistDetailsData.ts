/**
 * useArtistDetailsData Hook
 *
 * Manages artist data fetching and state
 */

import type { Artist as DomainArtist, DetailTrack } from '@/types/domain';
import type { ArtistDetailApiResponse } from '@/api/transformers/types';
import { transformArtistDetail } from '@/api/transformers/artistTransformer';
import { useAbortableResource } from '@/hooks/shared/useAbortableResource';
import { get } from '@/utils/apiRequest';
import { isArtistDetailShape } from '@/api/responseGuards';
import { getArtistTracks, type TrackInArtist } from '@/services/libraryService';

export interface Album {
  id: number;
  title: string;
  year?: number;
  track_count: number;
  total_duration: number;
  /** Present only when the album has artwork (#5925); AlbumsTab requests the cover from it. */
  artwork_url?: string | null;
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

/** The artist detail plus its own track list (#6009); a failed track list is not fatal. */
const fetchArtist = async (artistId: number, signal: AbortSignal): Promise<Artist> => {
  // #4643: through the shared get()/ApiErrorHandler transport, so a 404 and a 500 stay
  // distinguishable for the UI's recovery action.
  const [data, trackList] = await Promise.all([
    get<ArtistDetailApiResponse>(`/api/artists/${artistId}`, { signal, validate: isArtistDetailShape }),
    getArtistTracks(artistId, signal).catch((err) => {
      if (!signal.aborted) console.error('Error fetching artist tracks:', err);
      return null;
    }),
  ]);
  const base = transformArtistDetail(data);
  return {
    ...base,
    albums: (data.albums || []).map((a) => ({
      id: a.id,
      title: a.title,
      year: a.year ?? undefined,
      track_count: a.track_count,
      total_duration: a.total_duration ?? 0,
      artwork_url: a.artwork_url ?? null,
    })),
    tracks: (trackList?.tracks ?? []).map((t) => toDetailTrack(t, base.name)),
  };
};

export const useArtistDetailsData = (artistId: number) => {
  const { data: artist, loading, error } = useAbortableResource<Artist>(
    artistId,
    (signal) => fetchArtist(artistId, signal),
    { label: 'artist details' },
  );
  return { artist, loading, error };
};
