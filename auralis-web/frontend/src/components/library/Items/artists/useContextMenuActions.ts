import { useMemo, useCallback, useState } from 'react';
import { getArtistContextActions } from '../../../shared/ContextMenu';
import { useToast } from '../../../shared/Toast';
import { getArtistTracks } from '../../../../services/libraryService';
import { useQueue } from '../../../../hooks/shared/useReduxState';
import { usePlayer } from '../../../../hooks/shared/useReduxState';
import type { Artist } from '@/types/domain';

interface UseContextMenuActionsProps {
  artist: Artist | null;
  onArtistClick?: (artistId: number, artistName: string) => void;
}

/**
 * useContextMenuActions - Generates context menu actions for artist
 *
 * Creates artist actions with toast notifications and callbacks.
 * Manages artist info modal state.
 * Memoized to prevent unnecessary re-renders.
 */
export const useContextMenuActions = ({
  artist,
  onArtistClick,
}: UseContextMenuActionsProps) => {
  const { success, error: showError } = useToast();
  const queue = useQueue();
  const player = usePlayer();
  const [infoModalOpen, setInfoModalOpen] = useState(false);

  const handlePlayAll = useCallback(async () => {
    if (!artist) return;

    try {
      // Fetch all tracks for the artist
      const response = await getArtistTracks(artist.id);

      if (response.tracks.length === 0) {
        showError(`No tracks found for ${artist.name}`);
        return;
      }

      // Convert API tracks to queue track format
      const tracks = response.tracks.map((track) => ({
        id: track.id,
        title: track.title,
        album: track.album,
        duration: track.duration,
      }));

      // Clear existing queue and set new tracks
      queue.clear();
      queue.setQueue(tracks as any);

      // Start playback
      player.play();

      success(`Playing all songs by ${artist.name}`);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to play artist tracks';
      showError(errorMessage);
    }
  }, [artist, queue, player, success, showError]);

  const handleAddToQueue = useCallback(async () => {
    if (!artist) return;

    try {
      success(`Added ${artist.name} to queue`);

      // Fetch all tracks for the artist
      const response = await getArtistTracks(artist.id);
      const tracks = response.tracks.map((track) => ({
        id: track.id,
        title: track.title,
        album: track.album,
        duration: track.duration,
      }));

      if (tracks.length === 0) {
        showError(`No tracks found for ${artist.name}`);
        return;
      }

      // Add all tracks to queue
      queue.addMany(tracks as any);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to add artist tracks to queue';
      showError(errorMessage);
    }
  }, [artist, queue, success, showError]);

  return useMemo(() => {
    if (!artist) {
      return {
        actions: [],
        modal: {
          open: false,
          artist: null,
          onClose: () => {},
        },
      };
    }

    return {
      actions: getArtistContextActions(artist.id, {
        onPlayAll: handlePlayAll,
        onAddToQueue: handleAddToQueue,
        onShowAlbums: () => {
          if (onArtistClick) {
            onArtistClick(artist.id, artist.name);
          }
        },
        onShowInfo: () => {
          setInfoModalOpen(true);
        },
      }),
      modal: {
        open: infoModalOpen,
        artist,
        onClose: () => setInfoModalOpen(false),
      },
    };
  }, [artist, onArtistClick, handlePlayAll, handleAddToQueue, infoModalOpen]);
};
