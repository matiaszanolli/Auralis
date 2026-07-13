import { useCallback, useMemo, useRef, useState } from 'react';
import { post, del } from '@/utils/apiRequest';
import { ENDPOINTS } from '@/config/api';
import { useToast } from '@/components/shared/Toast';
import { addTracksToPlaylist } from '@/services/playlistService';

interface UseBatchOperationsProps {
  selectedTracks: Set<number>;
  selectedCount: number;
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
  onFetchTracks,
  onClearSelection,
}: UseBatchOperationsProps) => {
  const { success, error } = useToast();

  // In-flight guard (#4443): bulk handlers fire N concurrent requests; a quick
  // double-click (or an interaction while a prior toast lingers) previously
  // fired a second full batch — duplicate favorite flips / queue insertions.
  // The ref blocks re-entrancy synchronously (state updates are async); the
  // state drives the toolbar's disabled UI.
  const isSubmittingRef = useRef(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const runExclusive = useCallback(async (op: () => Promise<void>): Promise<void> => {
    if (isSubmittingRef.current) return; // re-entrant call while a batch is in flight → no-op
    isSubmittingRef.current = true;
    setIsSubmitting(true);
    try {
      await op();
    } finally {
      isSubmittingRef.current = false;
      setIsSubmitting(false);
    }
  }, []);

  const handleBulkAddToQueue = useCallback(() => runExclusive(async () => {
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
  }), [runExclusive, selectedTracks, onClearSelection, success, error]);

  const handleBulkAddToPlaylist = useCallback((playlistId: number, playlistName: string) => runExclusive(async () => {
    const trackIds = Array.from(selectedTracks);
    try {
      const addedCount = await addTracksToPlaylist(playlistId, trackIds);
      if (addedCount === trackIds.length) {
        success(`Added ${addedCount} track${addedCount !== 1 ? 's' : ''} to "${playlistName}"`);
      } else if (addedCount === 0) {
        error(`Failed to add tracks to "${playlistName}"`);
      } else {
        error(`Added ${addedCount} of ${trackIds.length} tracks to "${playlistName}"`);
      }
    } catch {
      error(`Failed to add tracks to "${playlistName}"`);
    }

    onClearSelection();
  }), [runExclusive, selectedTracks, onClearSelection, success, error]);

  // Bulk remove is only wired for the favourites context — non-favourites
  // library removal has no backend deletion route yet (fixes #4240; the
  // toolbar's Remove button is hidden outside favourites so this branch
  // is unreachable rather than a silent no-op toast).
  const handleBulkRemove = useCallback(() => runExclusive(async () => {
    if (!confirm(`Remove ${selectedCount} tracks?`)) {
      return;
    }

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

    onClearSelection();
    await onFetchTracks();
  }), [runExclusive, selectedTracks, selectedCount, onClearSelection, onFetchTracks, success, error]);

  const handleBulkToggleFavorite = useCallback(() => runExclusive(async () => {
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
  }), [runExclusive, selectedTracks, onClearSelection, onFetchTracks, success, error]);

  return useMemo(() => ({
    handleBulkAddToQueue,
    handleBulkAddToPlaylist,
    handleBulkRemove,
    handleBulkToggleFavorite,
    isSubmitting,
  }), [handleBulkAddToQueue, handleBulkAddToPlaylist, handleBulkRemove, handleBulkToggleFavorite, isSubmitting]);
};
