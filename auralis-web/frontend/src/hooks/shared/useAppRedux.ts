/**
 * App-Level Redux Hooks
 * ~~~~~~~~~~~~~~~~~~~~~
 *
 * Hooks that read across several Redux slices at once. Split out of
 * useReduxState.ts (#5239), which re-exports everything here.
 *
 * @copyright (C) 2024 Auralis Team
 * @license AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
 */

import { usePlayerState } from '@/hooks/shared/usePlayerRedux';
import { useQueueState } from '@/hooks/shared/useQueueRedux';
import { useCacheState } from '@/hooks/shared/useCacheRedux';
import { useConnectionState } from '@/hooks/shared/useConnectionRedux';

/**
 * Access complete application state in one hook
 * Useful for complex components needing multiple slices
 */
export const useAppState = () => {
  const player = usePlayerState();
  const queue = useQueueState();
  const cache = useCacheState();
  const connection = useConnectionState();

  return {
    player,
    queue,
    cache,
    connection,
  };
};

// #5354: useIsLoading()/useAppErrors() were deleted — zero production callers,
// reading player/queue/cache isLoading/error fields that nothing ever
// dispatched, so they could only ever report "idle, no errors".
