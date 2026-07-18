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
  /** Reorder entire queue by track IDs */
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

  const setQueue = useCallback(
    async (tracks: Track[], startIndex: number = 0): Promise<void> => {
      setIsLoading(true);
      setError(null);

      const previousTracks = stateRef.current.tracks;
      const previousIndex = stateRef.current.currentIndex;

      dispatch(reduxSetQueue(tracks));
      dispatch(reduxSetCurrentIndex(startIndex));

      try {
        await post('/api/player/queue', {
          tracks: tracks.map((t) => t.id),
          start_index: startIndex,
        });
      } catch (err) {
        dispatch(reduxSetQueue(previousTracks));
        dispatch(reduxSetCurrentIndex(previousIndex));

        const apiError = ApiErrorHandler.parseWithCode(err, 'QUEUE_SET_ERROR');
        setError(apiError);
        throw apiError;
      } finally {
        setIsLoading(false);
      }
    },
    [post, dispatch]
  );

  const addTrack = useCallback(
    async (track: Track, position?: number): Promise<void> => {
      setIsLoading(true);
      setError(null);

      try {
        await post('/api/player/queue/add-track', {
          track_id: track.id,
          position: position !== undefined ? position : undefined,
        });
      } catch (err) {
        const apiError = ApiErrorHandler.parseWithCode(err, 'ADD_TRACK_ERROR');
        setError(apiError);
        throw apiError;
      } finally {
        setIsLoading(false);
      }
    },
    [post]
  );

  const removeTrack = useCallback(
    async (index: number): Promise<void> => {
      setIsLoading(true);
      setError(null);

      try {
        await apiDelete(`/api/player/queue/${index}`);
      } catch (err) {
        const apiError = ApiErrorHandler.parseWithCode(err, 'REMOVE_TRACK_ERROR');
        setError(apiError);
        throw apiError;
      } finally {
        setIsLoading(false);
      }
    },
    [apiDelete]
  );

  const reorderTrack = useCallback(
    async (fromIndex: number, toIndex: number): Promise<void> => {
      setIsLoading(true);
      setError(null);

      try {
        await put('/api/player/queue/reorder', {
          from_index: fromIndex,
          to_index: toIndex,
        });
      } catch (err) {
        const apiError = ApiErrorHandler.parseWithCode(err, 'REORDER_ERROR');
        setError(apiError);
        throw apiError;
      } finally {
        setIsLoading(false);
      }
    },
    [put]
  );

  const reorderQueue = useCallback(
    async (newOrder: number[]): Promise<void> => {
      setIsLoading(true);
      setError(null);

      try {
        await put('/api/player/queue/reorder', {
          new_order: newOrder,
        });
      } catch (err) {
        const apiError = ApiErrorHandler.parseWithCode(err, 'REORDER_QUEUE_ERROR');
        setError(apiError);
        throw apiError;
      } finally {
        setIsLoading(false);
      }
    },
    [put]
  );

  const toggleShuffle = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);

    const newShuffle = !stateRef.current.isShuffled;
    const previousShuffle = stateRef.current.isShuffled;

    dispatch(reduxSetIsShuffled(newShuffle));

    try {
      // Send enabled as query param — backend reads it as ?enabled=true/false
      await post('/api/player/queue/shuffle', undefined, {
        enabled: newShuffle,
      });
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
      setIsLoading(true);
      setError(null);

      if (!['off', 'all', 'one'].includes(mode)) {
        const apiError = {
          message: `Invalid repeat mode: ${mode}`,
          code: 'INVALID_REPEAT_MODE',
          status: 400,
        };
        setError(apiError);
        throw apiError;
      }

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

  const clearQueue = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);

    const previousTracks = stateRef.current.tracks;
    const previousIndex = stateRef.current.currentIndex;

    dispatch(reduxClearQueue());

    try {
      await post('/api/player/queue/clear');
    } catch (err) {
      dispatch(reduxSetQueue(previousTracks));
      dispatch(reduxSetCurrentIndex(previousIndex));

      const apiError = ApiErrorHandler.parseWithCode(err, 'CLEAR_QUEUE_ERROR');
      setError(apiError);
      throw apiError;
    } finally {
      setIsLoading(false);
    }
  }, [post, dispatch]);

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
