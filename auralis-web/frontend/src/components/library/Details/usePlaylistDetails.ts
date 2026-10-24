/**
 * usePlaylistDetails Hook
 *
 * Fetches a single playlist with its tracks for PlaylistDetailView.
 * GET /api/playlists/{id} returns the playlist with every track eagerly
 * loaded (#5606 transform applied in playlistService.getPlaylist), so one
 * request covers both the header and the track table — no pagination to
 * drive, unlike the songs/favourites views.
 */

import { useState, useEffect } from 'react';
import type { Playlist } from '@/services/playlistService';
import type { ApiError } from '@/types/api';
import { ApiErrorHandler } from '@/types/api';
import { getPlaylist } from '@/services/playlistService';
import { isAbortError } from '@/utils/errorGuards';

export const usePlaylistDetails = (playlistId: number) => {
  const [playlist, setPlaylist] = useState<Playlist | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getPlaylist(playlistId, controller.signal);
        if (controller.signal.aborted) return;
        setPlaylist(data);
      } catch (err) {
        // Same abort semantics as useAlbumDetails (#3601/#4643): the signal
        // is authoritative regardless of how the transport shapes an abort.
        if (controller.signal.aborted || isAbortError(err)) return;
        console.error('Error fetching playlist details:', err);
        setError(ApiErrorHandler.parse(err));
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    };
    run();
    return () => controller.abort();
  }, [playlistId]);

  return { playlist, loading, error };
};
