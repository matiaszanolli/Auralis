import { useMemo } from 'react';
import { getPlaylistContextActions } from '@/components/shared/ContextMenu';
import { useToast } from '@/components/shared/Toast';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { usePlaybackQueue } from '@/hooks/player/usePlaybackQueue';
import * as playlistService from '@/services/playlistService';

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
  const { info, success, error: errorToast } = useToast();
  const { setQueue } = usePlaybackQueue();
  const wsContext = useWebSocketContext();

  return useMemo(() => {
    if (!playlist) return [];

    return getPlaylistContextActions(playlist.id.toString(), {
      onPlay: async () => {
        try {
          // Fetch the playlist's tracks, replace the queue, then start the
          // first track (#4040 — previously a stub that only toasted/navigated).
          const full = await playlistService.getPlaylist(playlist.id);
          const tracks = full.tracks ?? [];
          if (tracks.length === 0) {
            info(`Playlist "${playlist.name}" has no tracks`);
            return;
          }

          // setQueue dispatches the Redux queue action AND posts to the backend.
          await setQueue(tracks, 0);
          // Begin playback of the first track; the Player's usePlayEnhanced
          // instance handles the stream and Redux syncs via player_state.
          wsContext.send({
            type: 'play_enhanced',
            data: { track_id: tracks[0].id, preset: 'adaptive', intensity: 1.0 },
          });

          success(`Playing playlist: ${playlist.name}`);
          if (onPlaylistSelect) {
            onPlaylistSelect(playlist.id);
          }
        } catch (err) {
          console.error('Failed to play playlist:', err);
          errorToast(`Failed to play playlist "${playlist.name}"`);
        }
      },
      onEdit: () => {
        onEdit(playlist);
      },
      onDelete: () => {
        onDelete(playlist.id, playlist.name);
      },
    });
  }, [playlist, onPlaylistSelect, onDelete, onEdit, info, success, errorToast, setQueue, wsContext]);
};
