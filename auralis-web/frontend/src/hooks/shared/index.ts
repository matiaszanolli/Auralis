/**
 * Shared utility hooks for common UI and data patterns
 * - Optimistic updates and state management
 * - Scroll animations and performance optimization
 * - Redux state management
 * - Artist grouping and data organization
 */

export { useDialogAccessibility } from './useDialogAccessibility';
export { useOptimisticUpdate } from './useOptimisticUpdate';
export { useScrollAnimation } from './useScrollAnimation';
export { useStandardizedAPI } from './useStandardizedAPI';
export { useVisualizationOptimization } from './useVisualizationOptimization';
export { useGroupedArtists } from './useGroupedArtists';
// Redux state hooks - exported from useReduxState.ts
export {
  usePlayerState,
  usePlayer,
  useQueueState,
  useQueue,
  useCacheState,
  useCache,
  useConnectionState,
  useConnection,
  useAppState,
  useIsLoading,
  useAppErrors,
  useConnectionHealth,
  usePlaybackProgress,
  useQueueTimeRemaining,
} from './useReduxState';
