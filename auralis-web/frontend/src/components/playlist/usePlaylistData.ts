import { useCallback, useEffect, useRef, useState } from 'react';
import * as playlistService from '@/services/playlistService';
import { usePlaylistWebSocket } from './usePlaylistWebSocket';

const fetchPlaylists = async (): Promise<playlistService.Playlist[]> => {
  try {
    const response = await playlistService.getPlaylists();
    return response.playlists;
  } catch (fetchError) {
    console.error('Failed to load playlists:', fetchError);
    return [];
  }
};

/**
 * usePlaylistData - Owns the sidebar playlist list (#5480)
 *
 * Holds `playlists` and `loading`, loads the list on mount, and keeps it in
 * sync with the playlist_* WebSocket events. Components apply their own local
 * changes through `addPlaylist` / `removePlaylist` / `refresh`.
 */
export const usePlaylistData = () => {
  const [playlists, setPlaylists] = useState<playlistService.Playlist[]>([]);
  const [loading, setLoading] = useState(false);

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
    const loaded = await fetchPlaylists();
    if (!isMountedRef.current) return;
    setPlaylists(loaded);
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
      const loaded = await fetchPlaylists();
      if (!isMountedRef.current) return;
      setPlaylists(loaded);
      setLoading(false);
    };
    loadPlaylists();
  }, []);

  usePlaylistWebSocket({
    onPlaylistCreated: refresh,
    // A rename event carries only {playlist_id, action}, not the new name,
    // so re-fetch. Merging the payload into the playlist, as this used to,
    // left the old name and added a stray `action` field (#5480).
    onPlaylistUpdated: refresh,
    onPlaylistDeleted: removePlaylist,
    onPlaylistsRefresh: refresh,
  });

  return { playlists, loading, refresh, addPlaylist, removePlaylist };
};
