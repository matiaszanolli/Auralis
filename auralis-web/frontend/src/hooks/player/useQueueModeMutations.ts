/**
 * Mutations that change how the queue plays, not what it holds: shuffle and repeat. Split out of
 * useQueueMutations.ts (#6275); each rolls back its own field, not the queue array.
 *
 * @module hooks/player/useQueueModeMutations
 */

import { useCallback, useMemo } from 'react';
import { useDispatch } from 'react-redux';
import { useRestAPI } from '@/hooks/api/useRestAPI';
import {
  setIsShuffled as reduxSetIsShuffled,
  setRepeatMode as reduxSetRepeatMode,
} from '@/store/slices/queueSlice';
import type { RepeatMode } from '@/types/domain';
import type { AppDispatch } from '@/store';
import type { QueueMutationRunner } from './queueMutationRunner';

export function useQueueModeMutations({ runMutation, snapshot, setError }: QueueMutationRunner) {
  const { post } = useRestAPI();
  const dispatch = useDispatch<AppDispatch>();

  const toggleShuffle = useCallback((): Promise<void> => {
    const newShuffle = !snapshot().isShuffled;
    return runMutation({
      field: 'shuffle',
      errorCode: 'SHUFFLE_ERROR',
      capture: () => {
        const previous = snapshot().isShuffled;
        return () => dispatch(reduxSetIsShuffled(previous));
      },
      apply: () => dispatch(reduxSetIsShuffled(newShuffle)),
      // `enabled` is a JSON body field (ShuffleRequest), not a query param: passing it as the
      // 3rd argument sent no body at all and the endpoint 422'd every time (#4859).
      request: () => post('/api/player/queue/shuffle', { enabled: newShuffle }),
    });
  }, [post, dispatch, runMutation, snapshot]);

  const setRepeatMode = useCallback(
    (mode: RepeatMode): Promise<void> => {
      // Validate before any in-flight accounting: the old order set isLoading and then threw
      // on an invalid mode without clearing it, wedging every queue control behind a spinner.
      if (!['off', 'all', 'one'].includes(mode)) {
        const apiError = { message: `Invalid repeat mode: ${mode}`, code: 'INVALID_REPEAT_MODE', status: 400 };
        setError(apiError);
        return Promise.reject(apiError);
      }
      return runMutation({
        field: 'repeat',
        errorCode: 'REPEAT_MODE_ERROR',
        capture: () => {
          const previous = snapshot().repeatMode;
          return () => dispatch(reduxSetRepeatMode(previous));
        },
        apply: () => dispatch(reduxSetRepeatMode(mode)),
        request: () => post('/api/player/queue/repeat', { mode }),
      });
    },
    [post, dispatch, runMutation, snapshot, setError]
  );

  return useMemo(() => ({ toggleShuffle, setRepeatMode }), [toggleShuffle, setRepeatMode]);
}
