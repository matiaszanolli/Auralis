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

import { useSelector } from 'react-redux';
import type { RootState } from '@/store';
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

/**
 * Check if any loading is in progress
 */
export const useIsLoading = () => {
  const player = useSelector((state: RootState) => state.player.isLoading);
  const queue = useSelector((state: RootState) => state.queue.isLoading);
  const cache = useSelector((state: RootState) => state.cache.isLoading);

  return player || queue || cache;
};

/**
 * Check if any errors exist
 */
export const useAppErrors = () => {
  const playerError = useSelector((state: RootState) => state.player.error);
  const queueError = useSelector((state: RootState) => state.queue.error);
  const cacheError = useSelector((state: RootState) => state.cache.error);
  const connectionError = useSelector((state: RootState) => state.connection.lastError);

  return {
    playerError,
    queueError,
    cacheError,
    connectionError,
    hasErrors: !!(playerError || queueError || cacheError || connectionError),
  };
};
