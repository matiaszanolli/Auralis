import { useCallback } from 'react';
import { useToast } from '../shared/Toast';

interface UseBatchOperationsProps {
  selectedTracks: Set<number>;
  selectedCount: number;
  view: string;
  onFetchTracks: () => Promise<void>;
  onClearSelection: () => void;
}

export const useBatchOperations = ({
  selectedTracks,
  selectedCount,
  view,
  onFetchTracks,
  onClearSelection,
}: UseBatchOperationsProps) => {
  const { success, error, info } = useToast();

  const handleBulkAddToQueue = useCallback(async () => {
    try {
      const selectedTrackIds = Array.from(selectedTracks);
      for (const trackId of selectedTrackIds) {
        await fetch('/api/player/queue/add-track', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ track_id: trackId })
        });
      }
      success(`Added ${selectedCount} tracks to queue`);
      onClearSelection();
    } catch (err) {
      error('Failed to add tracks to queue');
    }
  }, [selectedTracks, selectedCount, onClearSelection, success, error]);

  const handleBulkAddToPlaylist = useCallback(async () => {
    info('Bulk add to playlist - Coming soon!');
  }, [info]);

  const handleBulkRemove = useCallback(async () => {
    if (!confirm(`Remove ${selectedCount} tracks?`)) {
      return;
    }

    try {
      if (view === 'favourites') {
        for (const trackId of selectedTracks) {
          await fetch(`/api/library/tracks/${trackId}/favorite`, {
            method: 'DELETE'
          });
        }
        success(`Removed ${selectedCount} tracks from favorites`);
      } else {
        info('Bulk delete from library requires API implementation');
      }

      onClearSelection();
      await onFetchTracks();
    } catch (err) {
      error('Failed to remove tracks');
    }
  }, [selectedTracks, selectedCount, view, onClearSelection, onFetchTracks, success, error, info]);

  const handleBulkToggleFavorite = useCallback(async () => {
    try {
      for (const trackId of selectedTracks) {
        await fetch(`/api/library/tracks/${trackId}/favorite`, {
          method: 'POST'
        });
      }
      success(`Toggled favorite for ${selectedCount} tracks`);
      onClearSelection();
      await onFetchTracks();
    } catch (err) {
      error('Failed to toggle favorites');
    }
  }, [selectedTracks, selectedCount, onClearSelection, onFetchTracks, success, error]);

  return {
    handleBulkAddToQueue,
    handleBulkAddToPlaylist,
    handleBulkRemove,
    handleBulkToggleFavorite,
  };
};
