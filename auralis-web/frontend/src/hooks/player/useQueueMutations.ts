/**
 * useQueueMutations Hook
 * ~~~~~~~~~~~~~~~~~~~~~~
 *
 * Queue mutation actions (set/add/remove/reorder/shuffle/repeat/clear) with
 * optimistic Redux updates and rollback-on-error. Extracted from
 * usePlaybackQueue (#4292) to keep the composing hook under the project's
 * 300-line module convention.
 *
 * @module hooks/player/useQueueMutations
 */

import { useCallback, useMemo, useState, useRef } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useRestAPI } from '@/hooks/api/useRestAPI';
import {
  setQueue as reduxSetQueue,
  setCurrentIndex as reduxSetCurrentIndex,
  clearQueue as reduxClearQueue,
  setIsShuffled as reduxSetIsShuffled,
  setRepeatMode as reduxSetRepeatMode,
  addTrack as reduxAddTrack,
  removeTrack as reduxRemoveTrack,
  reorderTrack as reduxReorderTrack,
  selectQueueTracks,
  selectCurrentIndex,
  selectIsShuffled,
  selectRepeatMode,
} from '@/store/slices/queueSlice';
import type { Track, QueueTrack } from '@/types/domain';
import type { ApiError } from '@/types/api';
import { ApiErrorHandler } from '@/types/api';
import type { AppDispatch } from '@/store';

interface RollbackState {
  tracks: (Track | QueueTrack)[];
  currentIndex: number;
  isShuffled: boolean;
  repeatMode: 'off' | 'all' | 'one';
}

export interface QueueMutations {
  /** Set entire queue and optional start position */
  setQueue: (tracks: Track[], startIndex?: number) => Promise<void>;
  /** Add single track to queue */
  addTrack: (track: Track, position?: number) => Promise<void>;
  /** Remove track at index */
  removeTrack: (index: number) => Promise<void>;
  /** Reorder track from one position to another */
  reorderTrack: (fromIndex: number, toIndex: number) => Promise<void>;
  /**
   * Reorder the entire queue.
   *
   * `newOrder` is a permutation of queue *indices*, not track IDs — the
   * backend validates `set(new_order) == set(range(queue_size))` and builds
   * the new queue as `[tracks[i] for i in new_order]`.
   */
  reorderQueue: (newOrder: number[]) => Promise<void>;
  /** Toggle shuffle mode */
  toggleShuffle: () => Promise<void>;
  /** Set repeat mode */
  setRepeatMode: (mode: 'off' | 'all' | 'one') => Promise<void>;
  /** Clear entire queue */
  clearQueue: () => Promise<void>;
  /** True while a command is executing */
  isLoading: boolean;
  /** Last error from a command */
  error: ApiError | null;
  /** Clear error state */
  clearError: () => void;
}

/**
 * Queue mutation actions, with optimistic Redux updates rolled back on
 * request failure using a ref to the latest state (avoids stale-closure
 * rollbacks without adding state to every callback's dependency array).
 */
export function useQueueMutations(): QueueMutations {
  const { post, put, delete: apiDelete } = useRestAPI();
  const dispatch = useDispatch<AppDispatch>();

  const tracks = useSelector(selectQueueTracks);
  const currentIndex = useSelector(selectCurrentIndex);
  const isShuffled = useSelector(selectIsShuffled);
  const repeatMode = useSelector(selectRepeatMode);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const stateRef = useRef<RollbackState>({ tracks, currentIndex, isShuffled, repeatMode });
  stateRef.current = { tracks, currentIndex, isShuffled, repeatMode };

  /**
   * Run a queue-array mutation optimistically (#4583).
   *
   * `apply` dispatches the change to Redux immediately so the UI reflects it
   * before the request resolves; if the request rejects, the pre-mutation
   * snapshot taken from `stateRef` is restored and the parsed `ApiError` is
   * re-thrown to the caller.
   *
   * Every mutation that touches `tracks`/`currentIndex` goes through here, so
   * the hook's "optimistic updates and rollback-on-error" contract holds for
   * all of them rather than half. `toggleShuffle`/`setRepeatMode` keep their
   * own rollbacks — they restore a different field, not the queue array.
   *
   * The `queue_changed` broadcast that follows re-sets the whole array from
   * the server, so the optimistic state is corrected rather than compounded.
   */
  const runOptimistic = useCallback(
    async (
      apply: () => void,
      request: () => Promise<unknown>,
      errorCode: string
    ): Promise<void> => {
      setIsLoading(true);
      setError(null);

      const previousTracks = stateRef.current.tracks;
      const previousIndex = stateRef.current.currentIndex;

      apply();

      try {
        await request();
      } catch (err) {
        dispatch(reduxSetQueue(previousTracks));
        dispatch(reduxSetCurrentIndex(previousIndex));

        const apiError = ApiErrorHandler.parseWithCode(err, errorCode);
        setError(apiError);
        throw apiError;
      } finally {
        setIsLoading(false);
      }
    },
    [dispatch]
  );

  const setQueue = useCallback(
    (tracks: Track[], startIndex: number = 0): Promise<void> =>
      runOptimistic(
        () => {
          dispatch(reduxSetQueue(tracks));
          dispatch(reduxSetCurrentIndex(startIndex));
        },
        () =>
          post('/api/player/queue', {
            tracks: tracks.map((t) => t.id),
            start_index: startIndex,
          }),
        'QUEUE_SET_ERROR'
      ),
    [post, dispatch, runOptimistic]
  );

  const addTrack = useCallback(
    (track: Track, position?: number): Promise<void> =>
      runOptimistic(
        () => dispatch(reduxAddTrack(track, position)),
        () =>
          post('/api/player/queue/add-track', {
            track_id: track.id,
            position,
          }),
        'ADD_TRACK_ERROR'
      ),
    [post, dispatch, runOptimistic]
  );

  const removeTrack = useCallback(
    (index: number): Promise<void> =>
      runOptimistic(
        () => dispatch(reduxRemoveTrack(index)),
        () => apiDelete(`/api/player/queue/${index}`),
        'REMOVE_TRACK_ERROR'
      ),
    [apiDelete, dispatch, runOptimistic]
  );

  const reorderTrack = useCallback(
    (fromIndex: number, toIndex: number): Promise<void> =>
      runOptimistic(
        () => dispatch(reduxReorderTrack({ fromIndex, toIndex })),
        () =>
          put('/api/player/queue/reorder', {
            from_index: fromIndex,
            to_index: toIndex,
          }),
        'REORDER_ERROR'
      ),
    [put, dispatch, runOptimistic]
  );

  const reorderQueue = useCallback(
    (newOrder: number[]): Promise<void> =>
      runOptimistic(
        () => {
          const previous = stateRef.current.tracks;
          // `newOrder` is a permutation of indices; mirror the backend's
          // `[tracks[i] for i in new_order]`. Anything the backend would
          // reject is left un-applied so the request produces the error
          // rather than a bogus optimistic state.
          if (newOrder.length !== previous.length) return;
          const reordered = newOrder.map((i) => previous[i]);
          if (reordered.some((t) => t === undefined)) return;

          // The backend keeps the current pointer on the same *track*
          // (queue_manager.reorder_tracks, #2159) rather than the same index.
          const currentId = previous[stateRef.current.currentIndex]?.id;
          dispatch(reduxSetQueue(reordered));
          const nextIndex =
            currentId === undefined ? 0 : reordered.findIndex((t) => t.id === currentId);
          dispatch(reduxSetCurrentIndex(nextIndex >= 0 ? nextIndex : 0));
        },
        () =>
          put('/api/player/queue/reorder', {
            new_order: newOrder,
          }),
        'REORDER_QUEUE_ERROR'
      ),
    [put, dispatch, runOptimistic]
  );

  const toggleShuffle = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);

    const newShuffle = !stateRef.current.isShuffled;
    const previousShuffle = stateRef.current.isShuffled;

    dispatch(reduxSetIsShuffled(newShuffle));

    try {
      // `enabled` is a JSON body field (ShuffleRequest), not a query param —
      // ac3f693a moved it body-side when closing #3174. Passing it as the 3rd
      // argument sent no body at all and the endpoint 422'd every time (#4859).
      // Mirrors queueService.shuffleQueue, which has always been correct.
      await post('/api/player/queue/shuffle', { enabled: newShuffle });
    } catch (err) {
      dispatch(reduxSetIsShuffled(previousShuffle));

      const apiError = ApiErrorHandler.parseWithCode(err, 'SHUFFLE_ERROR');
      setError(apiError);
      throw apiError;
    } finally {
      setIsLoading(false);
    }
  }, [post, dispatch]);

  const setRepeatMode = useCallback(
    async (mode: 'off' | 'all' | 'one'): Promise<void> => {
      // Validate before flipping isLoading: the old order set isLoading true
      // and then threw on an invalid mode without ever clearing it, wedging
      // every queue control behind a permanent loading state.
      if (!['off', 'all', 'one'].includes(mode)) {
        const apiError = {
          message: `Invalid repeat mode: ${mode}`,
          code: 'INVALID_REPEAT_MODE',
          status: 400,
        };
        setError(apiError);
        throw apiError;
      }

      setIsLoading(true);
      setError(null);

      const previousMode = stateRef.current.repeatMode;
      dispatch(reduxSetRepeatMode(mode));

      try {
        await post('/api/player/queue/repeat', { mode });
      } catch (err) {
        dispatch(reduxSetRepeatMode(previousMode));

        const apiError = ApiErrorHandler.parseWithCode(err, 'REPEAT_MODE_ERROR');
        setError(apiError);
        throw apiError;
      } finally {
        setIsLoading(false);
      }
    },
    [post, dispatch]
  );

  const clearQueue = useCallback(
    (): Promise<void> =>
      runOptimistic(
        () => dispatch(reduxClearQueue()),
        () => post('/api/player/queue/clear'),
        'CLEAR_QUEUE_ERROR'
      ),
    [post, dispatch, runOptimistic]
  );

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return useMemo(() => ({
    setQueue,
    addTrack,
    removeTrack,
    reorderTrack,
    reorderQueue,
    toggleShuffle,
    setRepeatMode,
    clearQueue,
    isLoading,
    error,
    clearError,
  }), [
    setQueue, addTrack, removeTrack, reorderTrack, reorderQueue,
    toggleShuffle, setRepeatMode, clearQueue, isLoading, error, clearError,
  ]);
}
