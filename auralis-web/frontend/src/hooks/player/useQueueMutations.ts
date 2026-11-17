/**
 * useQueueMutations Hook
 * ~~~~~~~~~~~~~~~~~~~~~~
 *
 * Queue mutation actions (set/add/remove/reorder/shuffle/repeat/clear) with optimistic Redux
 * updates and rollback-on-error. Extracted from usePlaybackQueue (#4292); the edit and mode
 * halves live in useQueueEditMutations / useQueueModeMutations (#6275) over one shared
 * optimistic-mutation loop (queueMutationRunner), and this hook only composes them.
 *
 * @module hooks/player/useQueueMutations
 */

import { useMemo } from 'react';
import { useQueueMutationRunner } from './queueMutationRunner';
import { useQueueEditMutations } from './useQueueEditMutations';
import { useQueueModeMutations } from './useQueueModeMutations';
import type { QueueMutations } from './queueMutationTypes';

export type { QueueMutations } from './queueMutationTypes';

export function useQueueMutations(): QueueMutations {
  const runner = useQueueMutationRunner();
  const edits = useQueueEditMutations(runner);
  const modes = useQueueModeMutations(runner);
  const { isLoading, error, clearError } = runner;

  return useMemo(
    () => ({ ...edits, ...modes, isLoading, error, clearError }),
    [edits, modes, isLoading, error, clearError]
  );
}
