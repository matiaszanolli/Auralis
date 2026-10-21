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
import { useDispatch, useStore } from 'react-redux';
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
  const store = useStore();

  // In-flight count, not a boolean (#5624): one shared boolean was cleared by
  // whichever mutation finished first, so with two overlapping mutations the
  // spinner dropped while the second was still in flight.
  const [inFlight, setInFlight] = useState(0);
  const isLoading = inFlight > 0;
  const [error, setError] = useState<ApiError | null>(null);

  const beginInFlight = useCallback(() => setInFlight((n) => n + 1), []);
  const endInFlight = useCallback(() => setInFlight((n) => n - 1), []);

  /**
   * Call-time snapshot of the queue fields (#5624).
   *
   * The snapshot used to come from a render-time ref, so two mutations
   * started in the same tick both captured the pre-first-mutation state: the
   * newest mutation's failure then rolled back past the earlier mutation's
   * already-applied-and-maybe-succeeded change. Reading the store at call
   * time sees every optimistically-applied mutation that preceded this one,
   * so a rollback restores exactly its own pre-state.
   */
  const snapshot = useCallback((): RollbackState => {
    const state = store.getState();
    return {
      tracks: selectQueueTracks(state),
      currentIndex: selectCurrentIndex(state),
      isShuffled: selectIsShuffled(state),
      repeatMode: selectRepeatMode(state),
    };
  }, [store]);

  /**
   * Per-field generation counters guarding stale rollbacks (#4836).
   *
   * A rollback restores a snapshot taken *before* its own mutation applied, so
   * if a later mutation has since applied (and possibly already succeeded), the
   * earlier mutation's failure would undo it too — for the queue that means a
   * whole-array overwrite discarding the later change entirely.
   *
   * Each mutation stamps its field's counter on entry and only rolls back if it
   * is still the newest mutation for that field. Counters are per-field rather
   * than global so a queue mutation cannot suppress a shuffle rollback, or vice
   * versa. A suppressed rollback still surfaces its error to the caller; the
   * server's `queue_changed` broadcast is what reconciles the state.
   */
  const generationRef = useRef({ queue: 0, shuffle: 0, repeat: 0 });

  const beginMutation = useCallback(
    (field: keyof typeof generationRef.current): number => (generationRef.current[field] += 1),
    []
  );

  const isNewestMutation = useCallback(
    (field: keyof typeof generationRef.current, generation: number): boolean =>
      generationRef.current[field] === generation,
    []
  );

  /**
   * Run a queue-array mutation optimistically (#4583).
   *
   * `apply` dispatches the change to Redux immediately so the UI reflects it
   * before the request resolves; if the request rejects, the pre-mutation
   * snapshot taken at call time from the store is restored and the parsed `ApiError` is
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
      beginInFlight();
      setError(null);

      const { tracks: previousTracks, currentIndex: previousIndex } = snapshot();
      const generation = beginMutation('queue');

      apply();

      try {
        await request();
      } catch (err) {
        // Only the newest queue mutation may restore its snapshot — an older
        // one would overwrite the whole array, discarding a later mutation
        // that has already applied and possibly succeeded (#4836).
        if (isNewestMutation('queue', generation)) {
          dispatch(reduxSetQueue(previousTracks));
          dispatch(reduxSetCurrentIndex(previousIndex));
        }

        const apiError = ApiErrorHandler.parseWithCode(err, errorCode);
        setError(apiError);
        throw apiError;
      } finally {
        endInFlight();
      }
    },
    [dispatch, beginMutation, isNewestMutation, beginInFlight, endInFlight, snapshot]
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
          // /queue/move takes MoveQueueTrackRequest {from_index, to_index} —
          // a single-item move. /queue/reorder takes ReorderQueueRequest
          // {new_order: int[]} and is used by reorderQueue below; sending this
          // payload there 422'd before the handler ever ran (#4854).
          put('/api/player/queue/move', {
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
          const { tracks: previous, currentIndex: previousIndex } = snapshot();
          // `newOrder` is a permutation of indices; mirror the backend's
          // `[tracks[i] for i in new_order]`. Anything the backend would
          // reject is left un-applied so the request produces the error
          // rather than a bogus optimistic state.
          if (newOrder.length !== previous.length) return;
          const reordered = newOrder.map((i) => previous[i]);
          if (reordered.some((t) => t === undefined)) return;

          // The backend keeps the current pointer on the same *track*
          // (queue_manager.reorder_tracks, #2159) rather than the same index.
          const currentId = previous[previousIndex]?.id;
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
    [put, dispatch, runOptimistic, snapshot]
  );

  const toggleShuffle = useCallback(async (): Promise<void> => {
    beginInFlight();
    setError(null);

    const { isShuffled: currentShuffle } = snapshot();
    const newShuffle = !currentShuffle;
    const previousShuffle = currentShuffle;
    const generation = beginMutation('shuffle');

    dispatch(reduxSetIsShuffled(newShuffle));

    try {
      // `enabled` is a JSON body field (ShuffleRequest), not a query param —
      // ac3f693a moved it body-side when closing #3174. Passing it as the 3rd
      // argument sent no body at all and the endpoint 422'd every time (#4859).
      // Mirrors queueService.shuffleQueue, which has always been correct.
      await post('/api/player/queue/shuffle', { enabled: newShuffle });
    } catch (err) {
      // Skip the rollback if a newer toggle has since applied (#4836).
      if (isNewestMutation('shuffle', generation)) {
        dispatch(reduxSetIsShuffled(previousShuffle));
      }

      const apiError = ApiErrorHandler.parseWithCode(err, 'SHUFFLE_ERROR');
      setError(apiError);
      throw apiError;
    } finally {
      endInFlight();
    }
  }, [post, dispatch, beginMutation, isNewestMutation, beginInFlight, endInFlight, snapshot]);

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

      beginInFlight();
      setError(null);

      const { repeatMode: previousMode } = snapshot();
      const generation = beginMutation('repeat');
      dispatch(reduxSetRepeatMode(mode));

      try {
        await post('/api/player/queue/repeat', { mode });
      } catch (err) {
        // Skip the rollback if a newer mode change has since applied (#4836).
        if (isNewestMutation('repeat', generation)) {
          dispatch(reduxSetRepeatMode(previousMode));
        }

        const apiError = ApiErrorHandler.parseWithCode(err, 'REPEAT_MODE_ERROR');
        setError(apiError);
        throw apiError;
      } finally {
        endInFlight();
      }
    },
    [post, dispatch, beginMutation, isNewestMutation, beginInFlight, endInFlight, snapshot]
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
