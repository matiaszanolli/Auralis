import { useState, useCallback, useMemo } from 'react';
import { getTrackContextActions } from '../../../shared/ContextMenu';
import { useToast } from '../../../shared/Toast';
import { useQueue } from '@/hooks/shared/useReduxState';
import * as playlistService from '@/services/playlistService';
import { Track } from './TrackRow';

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
  const { success, info, error } = useToast();
  const queue = useQueue();

  const fetchPlaylists = useCallback(async () => {
    setIsLoadingPlaylists(true);
    try {
      const response = await playlistService.getPlaylists();
      setPlaylists(response.playlists);
    } catch (err) {
      console.error('Failed to load playlists:', err);
    } finally {
      setIsLoadingPlaylists(false);
    }
  }, []);

  const handleAddToPlaylist = useCallback(
    async (playlistId: number, playlistName: string) => {
      try {
        await playlistService.addTracksToPlaylist(playlistId, [track.id]);
        success(`Added to "${playlistName}"`);
      } catch (err) {
        error(`Failed to add to playlist: ${err}`);
      }
    },
    [track.id, success, error]
  );

  const handleCreatePlaylist = useCallback(
    async (playlist: playlistService.Playlist) => {
      try {
        await playlistService.addTracksToPlaylist(playlist.id, [track.id]);
        success(`Added to "${playlist.name}"`);
      } catch (err) {
        error(`Failed to add to playlist: ${err}`);
      }
    },
    [track.id, success, error]
  );

  const handleAddToQueue = useCallback(() => {
    try {
      // Convert track to queue track format
      const queueTrack = {
        id: track.id,
        title: track.title,
        album: track.album,
        duration: track.duration,
      };

      // Add track to queue
      queue.addMany([queueTrack] as any);
      success(`Added "${track.title}" to queue`);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to add track to queue';
      error(errorMessage);
    }
  }, [track.id, track.title, track.album, track.duration, queue, success, error]);

  const handleMoreClick = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setContextMenuPosition({ top: e.clientY, left: e.clientX });
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
      getTrackContextActions(track.id, track.favorite || false, {
        onPlay: () => {
          onPlay(track.id);
          info(`Now playing: ${track.title}`);
        },
        onAddToQueue: handleAddToQueue,
        onAddToPlaylist: handleCloseContextMenu,
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
          onShowAlbum && track.album_id
            ? () => {
                onShowAlbum(track.album_id!);
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
      track.album_id,
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
      handleCloseContextMenu,
      handleAddToQueue,
    ]
  );

  return {
    contextMenuPosition,
    playlists,
    isLoadingPlaylists,
    handleMoreClick,
    handleTrackContextMenu,
    handleCloseContextMenu,
    fetchPlaylists,
    handleAddToPlaylist,
    handleCreatePlaylist,
    contextActions,
  };
};
