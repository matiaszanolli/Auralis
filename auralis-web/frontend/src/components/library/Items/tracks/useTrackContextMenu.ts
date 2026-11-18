import { useState, useCallback, useMemo } from 'react';
import { failureMessage } from '@/utils/errorGuards';
import { getTrackContextActions } from '@/components/shared/ContextMenu';
import { useToast } from '@/components/shared/Toast';
import * as playlistService from '@/services/playlistService';
import { addTrackToQueue } from '@/services/queueService';
import type { LibraryTrack as Track } from '@/types/domain';

export interface UseTrackContextMenuProps {
  track: Track;
  onPlay: (trackId: number) => void;
  onToggleFavorite?: (trackId: number) => void;
  onShowAlbum?: (albumId: number) => void;
  onShowArtist?: (artistName: string) => void;
  onShowInfo?: (trackId: number) => void;
  onFindSimilar?: (trackId: number) => void; // Phase 5: Find similar tracks callback
  onEditMetadata?: (trackId: number) => void;
  onDelete?: (trackId: number) => void;
}

/**
 * useTrackContextMenu - Manages track context menu state and actions
 *
 * Handles:
 * - Context menu position state
 * - Playlist fetching and operations
 * - Context menu actions generation
 * - Phase 5: Find similar tracks action
 */
export const useTrackContextMenu = ({
  track,
  onPlay,
  onToggleFavorite,
  onShowAlbum,
  onShowArtist,
  onShowInfo,
  onFindSimilar, // Phase 5: Find similar tracks callback
  onEditMetadata,
  onDelete,
}: UseTrackContextMenuProps) => {
  const [contextMenuPosition, setContextMenuPosition] = useState<{
    top: number;
    left: number;
  } | null>(null);
  const [playlists, setPlaylists] = useState<playlistService.Playlist[]>([]);
  const [isLoadingPlaylists, setIsLoadingPlaylists] = useState(false);
  // Lets a consumer tell "failed to load" from "no playlists" (#5645).
  const [playlistsFailed, setPlaylistsFailed] = useState(false);
  const { success, info, warning, error } = useToast();

  const fetchPlaylists = useCallback(async () => {
    setIsLoadingPlaylists(true);
    try {
      const response = await playlistService.getPlaylists();
      setPlaylists(response.playlists);
      setPlaylistsFailed(false);
    } catch (err) {
      console.error('Failed to load playlists:', err);
      setPlaylistsFailed(true);
    } finally {
      setIsLoadingPlaylists(false);
    }
  }, []);

  // The route answers 200 with added_count 0 for an all-duplicate request, so the count - not the
  // absence of an error - says whether the track went in (#6436).
  const handleAddToPlaylist = useCallback(
    async (playlistId: number, playlistName: string) => {
      try {
        const added = await playlistService.addTracksToPlaylist(playlistId, [track.id]);
        if (added > 0) success(`Added to "${playlistName}"`);
        else warning(`Nothing was added to "${playlistName}"`);
      } catch (err) {
        error(failureMessage('Failed to add to playlist', err));
      }
    },
    [track.id, success, warning, error]
  );

  const handleCreatePlaylist = useCallback(
    (playlist: playlistService.Playlist) => handleAddToPlaylist(playlist.id, playlist.name),
    [handleAddToPlaylist]
  );

  // #5612: this used to dispatch to the Redux queue only, so the engine never
  // heard about the track yet a success toast was shown. The backend call is
  // the source of truth; its queue_changed broadcast updates Redux, and the
  // toast waits for it.
  const handleAddToQueue = useCallback(async () => {
    try {
      await addTrackToQueue(track.id);
      success(`Added "${track.title}" to queue`);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to add track to queue';
      error(errorMessage);
    }
  }, [track.id, track.title, success, error]);

  // Anchored to the button, not the pointer: a keyboard-activated click
  // reports clientX/clientY 0, which flung the menu to the viewport origin
  // (#5658). For a pointer click the button is where the click landed anyway.
  const handleMoreClick = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    const rect = e.currentTarget.getBoundingClientRect();
    setContextMenuPosition({ top: rect.bottom, left: rect.left });
  }, []);

  const handleTrackContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenuPosition({ top: e.clientY, left: e.clientX });
  }, []);

  const handleCloseContextMenu = useCallback(() => {
    setContextMenuPosition(null);
  }, []);

  const contextActions = useMemo(
    () =>
      getTrackContextActions(track.favorite || false, {
        onPlay: () => {
          onPlay(track.id);
        },
        onAddToQueue: handleAddToQueue,
        onToggleLove: onToggleFavorite
          ? () => {
              onToggleFavorite(track.id);
              success(
                track.favorite
                  ? `Removed "${track.title}" from favorites`
                  : `Added "${track.title}" to favorites`
              );
            }
          : undefined,
        onShowAlbum:
          onShowAlbum && track.albumId
            ? () => {
                onShowAlbum(track.albumId!);
              }
            : undefined,
        onShowArtist: onShowArtist
          ? () => {
              onShowArtist(track.artist);
            }
          : undefined,
        onShowInfo: onShowInfo
          ? () => {
              onShowInfo(track.id);
            }
          : undefined,
        onFindSimilar: onFindSimilar // Phase 5: Find similar tracks action
          ? () => {
              onFindSimilar(track.id);
              info(`Finding tracks similar to "${track.title}"...`);
            }
          : undefined,
        onEditMetadata: onEditMetadata
          ? () => {
              onEditMetadata(track.id);
            }
          : undefined,
        onDelete: onDelete
          ? () => {
              onDelete(track.id);
            }
          : undefined,
      }),
    [
      track.id,
      track.title,
      track.favorite,
      track.albumId,
      track.artist,
      onPlay,
      onToggleFavorite,
      onShowAlbum,
      onShowArtist,
      onShowInfo,
      onFindSimilar, // Phase 5: Find similar tracks dependency
      onEditMetadata,
      onDelete,
      info,
      success,
      handleAddToQueue,
    ]
  );

  return {
    contextMenuPosition,
    playlists,
    isLoadingPlaylists,
    playlistsFailed,
    handleMoreClick,
    handleTrackContextMenu,
    handleCloseContextMenu,
    fetchPlaylists,
    handleAddToPlaylist,
    handleCreatePlaylist,
    contextActions,
  };
};
