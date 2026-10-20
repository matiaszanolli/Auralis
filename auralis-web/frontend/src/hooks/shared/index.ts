/**
 * Shared utility hooks for common UI and data patterns
 * - Optimistic updates and state management
 * - Redux state management
 * - Artist grouping and data organization
 */

export { useDialogAccessibility } from './useDialogAccessibility';
export { useOptimisticUpdate } from './useOptimisticUpdate';
export { useGroupedArtists } from './useGroupedArtists';
// Redux state hooks - exported from useReduxState.ts
export {
  usePlayerState,
  usePlayerActions,
  useQueueState,
  useQueue,
  useCacheState,
  useConnectionState,
  useConnection,
  useAppState,
  useConnectionHealth,
  useQueueTimeRemaining,
} from './useReduxState';
