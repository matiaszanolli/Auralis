/**
 * Mutations that change the queue's contents: set, add, remove, reorder, clear. Split out of
 * useQueueMutations.ts (#6275); shuffle and repeat are in useQueueModeMutations.ts.
 *
 * @module hooks/player/useQueueEditMutations
 */

import { useCallback, useMemo } from 'react';
import { useDispatch } from 'react-redux';
import { useRestAPI } from '@/hooks/api/useRestAPI';
import {
  setQueue as reduxSetQueue,
  setCurrentIndex as reduxSetCurrentIndex,
  clearQueue as reduxClearQueue,
  addTrack as reduxAddTrack,
  removeTrack as reduxRemoveTrack,
  reorderTrack as reduxReorderTrack,
} from '@/store/slices/queueSlice';
import type { Track } from '@/types/domain';
import type { AppDispatch } from '@/store';
import type { QueueMutationRunner } from './queueMutationRunner';

export function useQueueEditMutations({ runMutation, snapshot }: QueueMutationRunner) {
  const { post, put, delete: apiDelete } = useRestAPI();
  const dispatch = useDispatch<AppDispatch>();

  /** Every edit rolls back the same way: restore the tracks and the current index. */
  const runEdit = useCallback(
    (apply: () => void, request: () => Promise<unknown>, errorCode: string): Promise<void> =>
      runMutation({
        field: 'queue',
        errorCode,
        apply,
        request,
        capture: () => {
          const { tracks, currentIndex } = snapshot();
          return () => {
            dispatch(reduxSetQueue(tracks));
            dispatch(reduxSetCurrentIndex(currentIndex));
          };
        },
      }),
    [runMutation, snapshot, dispatch]
  );

  const setQueue = useCallback(
    (tracks: Track[], startIndex: number = 0): Promise<void> =>
      runEdit(
        () => {
          dispatch(reduxSetQueue(tracks));
          dispatch(reduxSetCurrentIndex(startIndex));
        },
        () => post('/api/player/queue', { tracks: tracks.map((t) => t.id), start_index: startIndex }),
        'QUEUE_SET_ERROR'
      ),
    [post, dispatch, runEdit]
  );

  const addTrack = useCallback(
    (track: Track, position?: number): Promise<void> =>
      runEdit(
        () => dispatch(reduxAddTrack(track, position)),
        () => post('/api/player/queue/add-track', { track_id: track.id, position }),
        'ADD_TRACK_ERROR'
      ),
    [post, dispatch, runEdit]
  );

  const removeTrack = useCallback(
    (index: number): Promise<void> =>
      runEdit(
        () => dispatch(reduxRemoveTrack(index)),
        () => apiDelete(`/api/player/queue/${index}`),
        'REMOVE_TRACK_ERROR'
      ),
    [apiDelete, dispatch, runEdit]
  );

  const reorderTrack = useCallback(
    (fromIndex: number, toIndex: number): Promise<void> =>
      runEdit(
        () => dispatch(reduxReorderTrack({ fromIndex, toIndex })),
        // /queue/move takes MoveQueueTrackRequest {from_index, to_index} - a single-item move.
        // /queue/reorder takes {new_order: int[]} (reorderQueue below); sending this payload
        // there 422'd before the handler ever ran (#4854).
        () => put('/api/player/queue/move', { from_index: fromIndex, to_index: toIndex }),
        'REORDER_ERROR'
      ),
    [put, dispatch, runEdit]
  );

  const reorderQueue = useCallback(
    (newOrder: number[]): Promise<void> =>
      runEdit(
        () => {
          const { tracks: previous, currentIndex: previousIndex } = snapshot();
          // `newOrder` is a permutation of indices; mirror the backend's
          // `[tracks[i] for i in new_order]`. Anything the backend would reject is left
          // un-applied so the request produces the error rather than a bogus optimistic state.
          if (newOrder.length !== previous.length) return;
          const reordered = newOrder.map((i) => previous[i]);
          if (reordered.some((t) => t === undefined)) return;

          // The backend keeps the current pointer on the same *track*
          // (queue_manager.reorder_tracks, #2159) rather than the same index.
          const currentId = previous[previousIndex]?.id;
          dispatch(reduxSetQueue(reordered));
          const nextIndex = currentId === undefined ? 0 : reordered.findIndex((t) => t.id === currentId);
          dispatch(reduxSetCurrentIndex(nextIndex >= 0 ? nextIndex : 0));
        },
        () => put('/api/player/queue/reorder', { new_order: newOrder }),
        'REORDER_QUEUE_ERROR'
      ),
    [put, dispatch, runEdit, snapshot]
  );

  const clearQueue = useCallback(
    (): Promise<void> =>
      runEdit(() => dispatch(reduxClearQueue()), () => post('/api/player/queue/clear'), 'CLEAR_QUEUE_ERROR'),
    [post, dispatch, runEdit]
  );

  return useMemo(
    () => ({ setQueue, addTrack, removeTrack, reorderTrack, reorderQueue, clearQueue }),
    [setQueue, addTrack, removeTrack, reorderTrack, reorderQueue, clearQueue]
  );
}
