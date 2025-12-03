import { useState, useCallback, useMemo } from 'react';
import { getTrackContextActions } from '../../../shared/ContextMenu';
import { useToast } from '../../../shared/Toast';
import * as playlistService from '@/services/playlistService';
import { Track } from './TrackRow';

export interface UseTrackContextMenuProps {
  track: Track;
  onPlay: (trackId: number) => void;
  onToggleFavorite?: (trackId: number) => void;
  onShowAlbum?: (albumId: number) => void;
  onShowArtist?: (artistName: string) => void;
  onShowInfo?: (trackId: number) => void;
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
 */
export const useTrackContextMenu = ({
  track,
  onPlay,
  onToggleFavorite,
  onShowAlbum,
  onShowArtist,
  onShowInfo,
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
        onAddToQueue: () => {
          success(`Added "${track.title}" to queue`);
          // TODO: Implement actual queue functionality
        },
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
      onEditMetadata,
      onDelete,
      info,
      success,
      handleCloseContextMenu,
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
