/**
 * The one optimistic-mutation loop every queue mutation runs through: in-flight accounting,
 * error state, call-time snapshot, generation-stamped rollback. Shared by the edit and mode
 * hooks (#6275); the guards it composes are in queueMutationGuards.ts.
 *
 * @module hooks/player/queueMutationRunner
 */

import { useCallback, useMemo, useState } from 'react';
import type { ApiError } from '@/types/api';
import { ApiErrorHandler } from '@/types/api';
import { useQueueMutationGuards } from './queueMutationGuards';
import type { MutationField } from './queueMutationGuards';

export interface MutationSpec {
  /** Which generation counter stamps this mutation (#4836). */
  field: MutationField;
  errorCode: string;
  /** Dispatch the optimistic change; runs after the pre-state was captured. */
  apply: () => void;
  request: () => Promise<unknown>;
  /** Called before `apply`; returns the function that restores the pre-mutation state. */
  capture: () => () => void;
}

export function useQueueMutationRunner() {
  const guards = useQueueMutationGuards();
  const { beginInFlight, endInFlight, beginMutation, isNewestMutation } = guards;
  const [error, setError] = useState<ApiError | null>(null);

  /**
   * Run a mutation optimistically (#4583): `apply` updates Redux at once; if the request
   * rejects, the pre-state captured at call time is restored - but only by the newest mutation
   * of its field, so an older failure cannot overwrite a later one that already applied and
   * possibly succeeded (#4836) - and the parsed `ApiError` is re-thrown. The `queue_changed`
   * broadcast that follows re-sets the server's state, so optimism is corrected, not compounded.
   */
  const runMutation = useCallback(
    async ({ field, errorCode, apply, request, capture }: MutationSpec): Promise<void> => {
      beginInFlight();
      setError(null);
      const restore = capture();
      const generation = beginMutation(field);
      apply();
      try {
        await request();
      } catch (err) {
        if (isNewestMutation(field, generation)) restore();
        const apiError = ApiErrorHandler.parseWithCode(err, errorCode);
        setError(apiError);
        throw apiError;
      } finally {
        endInFlight();
      }
    },
    [beginInFlight, endInFlight, beginMutation, isNewestMutation]
  );

  const clearError = useCallback(() => setError(null), []);

  return useMemo(
    () => ({ runMutation, snapshot: guards.snapshot, isLoading: guards.isLoading, error, setError, clearError }),
    [runMutation, guards.snapshot, guards.isLoading, error, clearError]
  );
}

export type QueueMutationRunner = ReturnType<typeof useQueueMutationRunner>;
