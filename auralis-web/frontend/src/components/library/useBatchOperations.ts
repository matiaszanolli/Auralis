import { useCallback } from 'react';
import { post, del } from '@/utils/apiRequest';
import { ENDPOINTS } from '@/config/api';
import { useToast } from '../shared/Toast';

interface UseBatchOperationsProps {
  selectedTracks: Set<number>;
  selectedCount: number;
  view: string;
  onFetchTracks: () => Promise<void>;
  onClearSelection: () => void;
}

/**
 * Report the outcome of a batch operation via toast.
 * Shows success if all passed, error if all failed, or a partial message otherwise.
 */
function reportBatchResult(
  results: PromiseSettledResult<unknown>[],
  successMsg: (n: number) => string,
  failMsg: string,
  toastSuccess: (msg: string) => void,
  toastError: (msg: string) => void
): void {
  const succeeded = results.filter(r => r.status === 'fulfilled').length;
  const failed = results.filter(r => r.status === 'rejected').length;

  if (failed === 0) {
    toastSuccess(successMsg(succeeded));
  } else if (succeeded === 0) {
    toastError(failMsg);
  } else {
    toastError(`${successMsg(succeeded)} — ${failed} failed`);
  }
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
    const trackIds = Array.from(selectedTracks);
    const results = await Promise.allSettled(
      trackIds.map(trackId => post(ENDPOINTS.QUEUE_ADD_TRACK, { track_id: trackId }))
    );

    reportBatchResult(
      results,
      n => `Added ${n} track${n !== 1 ? 's' : ''} to queue`,
      'Failed to add tracks to queue',
      success,
      error
    );

    onClearSelection();
  }, [selectedTracks, onClearSelection, success, error]);

  const handleBulkAddToPlaylist = useCallback(async () => {
    info('Bulk add to playlist - Coming soon!');
  }, [info]);

  const handleBulkRemove = useCallback(async () => {
    if (!confirm(`Remove ${selectedCount} tracks?`)) {
      return;
    }

    if (view === 'favourites') {
      const trackIds = Array.from(selectedTracks);
      const results = await Promise.allSettled(
        trackIds.map(trackId => del(ENDPOINTS.TRACK_FAVORITE(trackId)))
      );

      reportBatchResult(
        results,
        n => `Removed ${n} track${n !== 1 ? 's' : ''} from favorites`,
        'Failed to remove tracks from favorites',
        success,
        error
      );
    } else {
      info('Bulk delete from library requires API implementation');
    }

    onClearSelection();
    await onFetchTracks();
  }, [selectedTracks, selectedCount, view, onClearSelection, onFetchTracks, success, error, info]);

  const handleBulkToggleFavorite = useCallback(async () => {
    const trackIds = Array.from(selectedTracks);
    const results = await Promise.allSettled(
      trackIds.map(trackId => post(ENDPOINTS.TRACK_FAVORITE(trackId)))
    );

    reportBatchResult(
      results,
      n => `Toggled favorite for ${n} track${n !== 1 ? 's' : ''}`,
      'Failed to toggle favorites',
      success,
      error
    );

    onClearSelection();
    await onFetchTracks();
  }, [selectedTracks, onClearSelection, onFetchTracks, success, error]);

  return {
    handleBulkAddToQueue,
    handleBulkAddToPlaylist,
    handleBulkRemove,
    handleBulkToggleFavorite,
  };
};
