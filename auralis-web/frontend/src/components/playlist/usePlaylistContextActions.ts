import { useMemo } from 'react';
import { getPlaylistContextActions } from '@/components/shared/ContextMenu';
import { useToast } from '@/components/shared/Toast';
import { usePlaybackControls } from '@/contexts/PlaybackSessionContext';
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
  const { info, error: errorToast } = useToast();
  const { setQueue } = usePlaybackQueue();
  const { startTrack } = usePlaybackControls();

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
          // Begin through the shared session so enabled/preset/intensity remain
          // live and the UI does not report success before stream confirmation
          // (#4812/#4813/#4829).
          await startTrack(tracks[0].id);

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
  }, [playlist, onPlaylistSelect, onDelete, onEdit, info, errorToast, setQueue, startTrack]);
};
