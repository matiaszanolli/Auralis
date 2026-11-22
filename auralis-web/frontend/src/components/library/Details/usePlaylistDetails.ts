/**
 * usePlaylistDetails Hook
 *
 * Fetches a single playlist with its tracks for PlaylistDetailView.
 * GET /api/playlists/{id} returns the playlist with every track eagerly
 * loaded (#5606 transform applied in playlistService.getPlaylist), so one
 * request covers both the header and the track table — no pagination to
 * drive, unlike the songs/favourites views.
 */

import type { Playlist } from '@/services/playlistService';
import { getPlaylist } from '@/services/playlistService';
import { useAbortableResource } from '@/hooks/shared/useAbortableResource';

export const usePlaylistDetails = (playlistId: number) => {
  const { data: playlist, loading, error } = useAbortableResource<Playlist>(
    playlistId,
    (signal) => getPlaylist(playlistId, signal),
    { label: 'playlist details' },
  );
  return { playlist, loading, error };
};
