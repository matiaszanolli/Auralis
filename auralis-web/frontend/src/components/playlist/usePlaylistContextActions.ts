import { useMemo } from 'react';
import { getPlaylistContextActions } from '../shared/ContextMenu';
import { useToast } from '../shared/Toast';
import * as playlistService from '../../services/playlistService';

interface UsePlaylistContextActionsProps {
  playlist: playlistService.Playlist | null;
  onPlaylistSelect?: (playlistId: number) => void;
  onDelete: (playlistId: number, playlistName: string) => void;
  onEdit: (playlist: playlistService.Playlist) => void;
}

/**
 * usePlaylistContextActions - Generates context menu actions for playlist
 *
 * Creates playlist actions with toast notifications and callbacks.
 * Memoized to prevent unnecessary re-renders.
 */
export const usePlaylistContextActions = ({
  playlist,
  onPlaylistSelect,
  onDelete,
  onEdit,
}: UsePlaylistContextActionsProps) => {
  const { info } = useToast();

  return useMemo(() => {
    if (!playlist) return [];

    return getPlaylistContextActions(playlist.id.toString(), {
      onPlay: () => {
        info(`Playing playlist: ${playlist.name}`);
        if (onPlaylistSelect) {
          onPlaylistSelect(playlist.id);
        }
        // TODO: Implement play playlist
      },
      onEdit: () => {
        onEdit(playlist);
      },
      onDelete: () => {
        onDelete(playlist.id, playlist.name);
      },
    });
  }, [playlist, onPlaylistSelect, onDelete, onEdit, info]);
};
