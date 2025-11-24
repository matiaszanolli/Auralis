import { useCallback } from 'react';
import * as playlistService from '../../../services/playlistService';
import { useToast } from '../Toast';

interface UsePlaylistActionsProps {
  onAddToPlaylist?: (playlistId: number, playlistName: string) => Promise<void>;
  onCreatePlaylist?: (playlist: playlistService.Playlist) => Promise<void>;
  onClose: () => void;
  onCreateDialogOpen: () => void;
}

/**
 * usePlaylistActions - Handles playlist-related context menu actions
 *
 * Encapsulates playlist operations (add to playlist, create new) with
 * toast notifications for success/error feedback.
 */
export const usePlaylistActions = ({
  onAddToPlaylist,
  onCreatePlaylist,
  onClose,
  onCreateDialogOpen,
}: UsePlaylistActionsProps) => {
  const { success, error } = useToast();

  const handleAddToPlaylist = useCallback(
    async (playlistId: number, playlistName: string) => {
      if (!onAddToPlaylist) return;
      try {
        await onAddToPlaylist(playlistId, playlistName);
        success(`Added to "${playlistName}"`);
        onClose();
      } catch (err) {
        error(`Failed to add to playlist: ${err}`);
      }
    },
    [onAddToPlaylist, success, error, onClose]
  );

  const handleCreateNewPlaylist = useCallback(() => {
    onClose();
    onCreateDialogOpen();
  }, [onClose, onCreateDialogOpen]);

  const handlePlaylistCreated = useCallback(
    async (playlist: playlistService.Playlist) => {
      if (!onCreatePlaylist) return;
      try {
        await onCreatePlaylist(playlist);
        success(`Added to "${playlist.name}"`);
      } catch (err) {
        error(`Failed to add to playlist: ${err}`);
      }
    },
    [onCreatePlaylist, success, error]
  );

  return {
    handleAddToPlaylist,
    handleCreateNewPlaylist,
    handlePlaylistCreated,
  };
};
