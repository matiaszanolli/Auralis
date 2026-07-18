/**
 * usePlaybackQueue Hook
 * ~~~~~~~~~~~~~~~~~~~~~
 *
 * Provides queue management and playback order control.
 * Handles queue state, reordering, shuffle, repeat modes, and persistence.
 *
 * Usage:
 * ```typescript
 * const {
 *   queue,
 *   currentIndex,
 *   isShuffled,
 *   repeatMode,
 *   setQueue,
 *   addTrack,
 *   removeTrack,
 *   reorderTracks,
 *   toggleShuffle,
 *   setRepeatMode,
 *   clearQueue,
 *   isLoading,
 *   error
 * } = usePlaybackQueue();
 *
 * await setQueue([track1, track2, track3]);
 * await addTrack(track4);
 * await toggleShuffle();
 * ```
 *
 * Composed from three focused hooks (#4292):
 * - useQueueFetch — initial fetch on mount
 * - useQueueSubscription — real-time sync via WebSocket
 * - useQueueMutations — set/add/remove/reorder/shuffle/repeat/clear actions
 *
 * @module hooks/player/usePlaybackQueue
 */

import { useMemo } from 'react';
import { useSelector } from 'react-redux';
import { useQueueFetch } from './useQueueFetch';
import { useQueueSubscription } from './useQueueSubscription';
import { useQueueMutations } from './useQueueMutations';
import {
  selectQueueTracks,
  selectCurrentIndex,
  selectIsShuffled,
  selectRepeatMode,
  selectLastUpdated,
} from '@/store/slices/queueSlice';
import { selectCurrentQueueTrack } from '@/store/selectors';
import type { Track, QueueTrack } from '@/types/domain';
import type { ApiError } from '@/types/api';

/**
 * Queue state and metadata
 */
export interface QueueState {
  /** Tracks in queue */
  tracks: (Track | QueueTrack)[];

  /** Current index in queue (0-based) */
  currentIndex: number;

  /** Whether shuffle mode is enabled */
  isShuffled: boolean;

  /** Repeat mode: 'off' | 'all' | 'one' */
  repeatMode: 'off' | 'all' | 'one';

  /** Last update timestamp */
  lastUpdated: number;
}

/**
 * Return type for usePlaybackQueue hook
 */
export interface PlaybackQueueActions {
  /** Queue state and metadata */
  state: QueueState;

  /** Shortcut to queue.tracks */
  queue: (Track | QueueTrack)[];

  /** Current queue index */
  currentIndex: number;

  /** Current track in queue (or null) */
  currentTrack: Track | QueueTrack | null;

  /** Whether shuffle is enabled */
  isShuffled: boolean;

  /** Current repeat mode */
  repeatMode: 'off' | 'all' | 'one';

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
 * Hook for managing audio playback queue
 *
 * @returns Queue management actions and state
 *
 * @example
 * ```typescript
 * const { queue, currentIndex, addTrack, removeTrack } = usePlaybackQueue();
 *
 * // Add a track to the end of queue
 * await addTrack(myTrack);
 *
 * // Reorder tracks in queue
 * await reorderTrack(0, 3); // Move track from position 0 to 3
 *
 * // Toggle shuffle
 * await toggleShuffle();
 * ```
 */
export function usePlaybackQueue(): PlaybackQueueActions {
  // All queue state lives in Redux (single source of truth)
  const tracks = useSelector(selectQueueTracks);
  const currentIndex = useSelector(selectCurrentIndex);
  const currentTrack = useSelector(selectCurrentQueueTrack);
  const isShuffled = useSelector(selectIsShuffled);
  const repeatMode = useSelector(selectRepeatMode);
  const lastUpdated = useSelector(selectLastUpdated);

  // Compose a QueueState view from Redux (single source of truth)
  const state: QueueState = useMemo(() => ({
    tracks,
    currentIndex,
    isShuffled,
    repeatMode,
    lastUpdated,
  }), [tracks, currentIndex, isShuffled, repeatMode, lastUpdated]);

  // Subscribe to real-time queue updates via WebSocket (dispatches to Redux)
  useQueueSubscription();

  // Fetch initial queue state on mount (dispatches to Redux)
  useQueueFetch();

  const mutations = useQueueMutations();

  // Memoize return value so object identity is stable when deps haven't changed,
  // preventing cascading re-renders in consumers (fixes #2465).
  return useMemo(() => ({
    state,
    queue: state.tracks,
    currentIndex: state.currentIndex,
    currentTrack,
    isShuffled: state.isShuffled,
    repeatMode: state.repeatMode,
    ...mutations,
  }), [state, currentTrack, mutations]);
}

/**
 * Convenience hook for queue without write operations
 *
 * @example
 * ```typescript
 * const { queue, currentTrack, isShuffled } = usePlaybackQueueView();
 * ```
 */
export function usePlaybackQueueView() {
  const { queue, currentIndex, currentTrack, isShuffled, repeatMode } =
    usePlaybackQueue();

  return {
    queue,
    currentIndex,
    currentTrack,
    isShuffled,
    repeatMode,
  };
}
