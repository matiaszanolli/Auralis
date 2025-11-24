import { useCallback } from 'react';
import { useToast } from '../shared/Toast';
import * as playlistService from '../../services/playlistService';

interface UsePlaylistOperationsProps {
  selectedPlaylistId?: number;
  onPlaylistSelect?: (playlistId: number) => void;
}

/**
 * usePlaylistOperations - Handles playlist CRUD operations
 *
 * Encapsulates:
 * - Fetching playlists
 * - Deleting playlists
 * - Editing playlists
 * - Creating playlists
 * - Updating playlists
 *
 * Provides toast notifications for user feedback.
 */
export const usePlaylistOperations = ({
  selectedPlaylistId,
  onPlaylistSelect,
}: UsePlaylistOperationsProps) => {
  const { success, error, info } = useToast();

  const fetchPlaylists = useCallback(async () => {
    try {
      const response = await playlistService.getPlaylists();
      return response.playlists;
    } catch (fetchError) {
      console.error('Failed to load playlists:', fetchError);
      return [];
    }
  }, []);

  const handleDelete = useCallback(
    async (playlistId: number, playlistName: string) => {
      if (!window.confirm(`Delete playlist "${playlistName}"?`)) {
        return false;
      }

      try {
        await playlistService.deletePlaylist(playlistId);
        success(`Playlist "${playlistName}" deleted`);

        // Clear selection if deleted playlist was selected
        if (selectedPlaylistId === playlistId && onPlaylistSelect) {
          onPlaylistSelect(-1);
        }
        return true;
      } catch (err) {
        error(`Failed to delete playlist: ${err}`);
        return false;
      }
    },
    [selectedPlaylistId, onPlaylistSelect, success, error]
  );

  const handleEdit = useCallback((playlist: playlistService.Playlist) => {
    return playlist;
  }, []);

  const handlePlaylistCreated = useCallback((playlist: playlistService.Playlist) => {
    if (onPlaylistSelect) {
      onPlaylistSelect(playlist.id);
    }
  }, [onPlaylistSelect]);

  const handlePlaylistUpdated = useCallback(async () => {
    // Refresh playlists to get latest data
    return await fetchPlaylists();
  }, [fetchPlaylists]);

  return {
    fetchPlaylists,
    handleDelete,
    handleEdit,
    handlePlaylistCreated,
    handlePlaylistUpdated,
  };
};
