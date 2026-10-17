import { useCallback, useEffect, useRef, useState } from 'react';
import * as playlistService from '@/services/playlistService';
import { usePlaylistWebSocket } from './usePlaylistWebSocket';

const LOAD_ERROR = 'Failed to load playlists';

/**
 * usePlaylistData - Owns the sidebar playlist list (#5480)
 *
 * Holds `playlists`, `loading` and `error`, loads the list on mount, and keeps
 * it in sync with the playlist_* WebSocket events. Components apply their own
 * local changes through `addPlaylist` / `removePlaylist` / `refresh`.
 *
 * A failed fetch never touches `playlists` (#5645): it used to resolve to `[]`,
 * so one transient failure on a WebSocket-triggered refetch erased a list that
 * had loaded fine and the sidebar claimed "No playlists yet". `error` carries
 * the failure instead, and the next successful `refresh` clears it. `refresh`
 * itself never rejects, so it is safe as a bare WebSocket callback.
 */
export const usePlaylistData = () => {
  const [playlists, setPlaylists] = useState<playlistService.Playlist[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Guard post-await setState against unmount: the mount fetch and the WS
  // callbacks can resolve/fire after the component unmounts (#4156).
  const isMountedRef = useRef(true);
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const refresh = useCallback(async () => {
    try {
      const response = await playlistService.getPlaylists();
      if (!isMountedRef.current) return;
      setPlaylists(response.playlists);
      setError(null);
    } catch (fetchError) {
      console.error('Failed to load playlists:', fetchError);
      if (!isMountedRef.current) return;
      setError(LOAD_ERROR);
    }
  }, []);

  const addPlaylist = useCallback((playlist: playlistService.Playlist) => {
    setPlaylists((prev) => [...prev, playlist]);
  }, []);

  const removePlaylist = useCallback((playlistId: number) => {
    setPlaylists((prev) => prev.filter((p) => p.id !== playlistId));
  }, []);

  useEffect(() => {
    const loadPlaylists = async () => {
      setLoading(true);
      await refresh();
      if (!isMountedRef.current) return;
      setLoading(false);
    };
    loadPlaylists();
  }, [refresh]);

  usePlaylistWebSocket({
    onPlaylistCreated: refresh,
    // A rename event carries only {playlist_id, action}, not the new name,
    // so re-fetch. Merging the payload into the playlist, as this used to,
    // left the old name and added a stray `action` field (#5480).
    onPlaylistUpdated: refresh,
    onPlaylistDeleted: removePlaylist,
    onPlaylistsRefresh: refresh,
  });

  return { playlists, loading, error, refresh, addPlaylist, removePlaylist };
};
