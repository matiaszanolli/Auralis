import { useCallback } from 'react';
import { useToast } from '@/components/shared/Toast';
import * as playlistService from '@/services/playlistService';

interface UsePlaylistOperationsProps {
  selectedPlaylistId?: number;
  onPlaylistSelect?: (playlistId: number) => void;
}

/**
 * usePlaylistOperations - Playlist deletion with confirmation and toasts
 *
 * Fetching moved to usePlaylistData (#5480); creating and editing are owned
 * by CreatePlaylistDialog / EditPlaylistDialog.
 */
export const usePlaylistOperations = ({
  selectedPlaylistId,
  onPlaylistSelect,
}: UsePlaylistOperationsProps) => {
  const { success, error } = useToast();

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

  return { handleDelete };
};
