import { useMemo, useCallback, useState } from 'react';
import { getArtistContextActions } from '@/components/shared/ContextMenu';
import { useToast } from '@/components/shared/Toast';
import { usePlaybackControls } from '@/contexts/PlaybackSessionContext';
import { getArtistTracks } from '@/services/libraryService';
import { addTracksToQueue, setQueue } from '@/services/queueService';
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
 *
 * Queue actions go to the backend (the engine queue is authoritative); its
 * broadcasts mirror the result into Redux. They used to dispatch to the Redux
 * queue alone, so the engine never changed, "Play All" started no stream, and a
 * success toast was shown anyway (#5612).
 */
export const useContextMenuActions = ({
  artist,
  onArtistClick,
}: UseContextMenuActionsProps) => {
  const { success, error: showError } = useToast();
  // Controls only: the 10Hz position tick lives in a separate context (#5006).
  const { startTrack } = usePlaybackControls();
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

      // Replace the engine queue, then stream the first track. The browser
      // session streams from the track id; setIsPlaying alone starts nothing.
      const trackIds = response.tracks.map((track) => track.id);
      await setQueue(trackIds, 0);
      await startTrack(trackIds[0]);

      success(`Playing all songs by ${artist.name}`);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to play artist tracks';
      showError(errorMessage);
    }
  }, [artist, startTrack, success, showError]);

  const handleAddToQueue = useCallback(async () => {
    if (!artist) return;

    try {
      // Fetch all tracks for the artist
      const response = await getArtistTracks(artist.id);

      if (response.tracks.length === 0) {
        showError(`No tracks found for ${artist.name}`);
        return;
      }

      // One batch request (#5651): the backend appends under one lock in
      // `trackIds` order, so the artist's tracks keep album order, and one
      // `queue_changed` goes out instead of N whole-queue broadcasts. A
      // partial result is reported instead of a false success.
      let result: Awaited<ReturnType<typeof addTracksToQueue>>;
      try {
        result = await addTracksToQueue(response.tracks.map((track) => track.id));
      } catch (err) {
        showError(err instanceof Error ? err.message : 'Failed to add artist tracks to queue');
        return;
      }
      if (result.added_count < result.requested_count) {
        showError(`Added ${result.added_count} of ${result.requested_count} tracks to queue`);
        return;
      }

      // Show success only after the tracks are actually added — previously this
      // fired before the fetch, so a failure/empty result produced a false
      // "Added…" toast immediately followed by an error toast. Mirrors
      // handlePlayAll, which shows success last (#4444).
      success(`Added ${artist.name} to queue`);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to add artist tracks to queue';
      showError(errorMessage);
    }
  }, [artist, success, showError]);

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
      actions: getArtistContextActions({
        onPlayAll: handlePlayAll,
        onAddToQueue: handleAddToQueue,
        // Absent without a navigation callback: the item would do nothing (#5614).
        onShowAlbums: onArtistClick
          ? () => {
              onArtistClick(artist.id, artist.name);
            }
          : undefined,
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
