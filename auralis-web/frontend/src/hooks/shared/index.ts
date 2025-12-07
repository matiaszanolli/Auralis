/**
 * Shared utility hooks for common UI and data patterns
 * - Infinite scrolling and pagination
 * - Optimistic updates and state management
 * - Scroll animations and performance optimization
 * - Redux state management
 */

export { useInfiniteScroll } from './useInfiniteScroll';
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
