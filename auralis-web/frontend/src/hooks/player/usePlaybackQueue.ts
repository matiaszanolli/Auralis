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
 * Features:
 * - Queue state management with persistence
 * - Track reordering and removal
 * - Shuffle mode (random playback order)
 * - Repeat modes (off, all, one)
 * - Real-time sync via WebSocket
 * - Optimistic UI updates with error rollback
 * - Memoized callbacks for performance
 *
 * @module hooks/player/usePlaybackQueue
 */

import { useCallback, useState, useEffect, useRef, useMemo } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useRestAPI } from '@/hooks/api/useRestAPI';
import { useWebSocketSubscription } from '@/hooks/websocket/useWebSocketSubscription';
import {
  setQueue as reduxSetQueue,
  setCurrentIndex as reduxSetCurrentIndex,
  clearQueue as reduxClearQueue,
  setIsShuffled as reduxSetIsShuffled,
  setRepeatMode as reduxSetRepeatMode,
  selectQueueTracks,
  selectCurrentIndex,
  selectCurrentQueueTrack,
  selectIsShuffled,
  selectRepeatMode,
} from '@/store/slices/queueSlice';
import type { Track, QueueTrack } from '@/types/domain';
import type { ApiError } from '@/types/api';

import type { AppDispatch } from '@/store';

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
  const { get, post, put, delete: apiDelete } = useRestAPI();
  const dispatch = useDispatch<AppDispatch>();

  // All queue state lives in Redux (single source of truth)
  const tracks = useSelector(selectQueueTracks);
  const currentIndex = useSelector(selectCurrentIndex);
  const currentTrack = useSelector(selectCurrentQueueTrack);
  const isShuffled = useSelector(selectIsShuffled);
  const repeatMode = useSelector(selectRepeatMode);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  // Compose a QueueState view for the public API
  const state: QueueState = useMemo(() => ({
    tracks,
    currentIndex,
    isShuffled,
    repeatMode,
    lastUpdated: Date.now(),
  }), [tracks, currentIndex, isShuffled, repeatMode]);

  /**
   * Ref to track latest state without causing callback recreation
   * Used for optimistic rollback in callbacks
   */
  const stateRef = useRef<QueueState>(state);
  stateRef.current = state;

  /**
   * Subscribe to real-time queue updates via WebSocket
   * Dispatch to Redux so all consumers see the same data.
   */
  useWebSocketSubscription(
    ['queue_changed', 'queue_shuffled', 'repeat_mode_changed'],
    (message) => {
      const { type, data } = message as any;

      switch (type) {
        case 'queue_changed':
          if (data.tracks) dispatch(reduxSetQueue(data.tracks));
          if (data.current_index != null) dispatch(reduxSetCurrentIndex(data.current_index));
          else if (data.currentIndex != null) dispatch(reduxSetCurrentIndex(data.currentIndex));
          break;

        case 'queue_shuffled':
          if (data.is_shuffled != null) dispatch(reduxSetIsShuffled(data.is_shuffled));
          else if (data.isShuffled != null) dispatch(reduxSetIsShuffled(data.isShuffled));
          if (data.tracks) dispatch(reduxSetQueue(data.tracks));
          break;

        case 'repeat_mode_changed':
          if (data.repeat_mode) dispatch(reduxSetRepeatMode(data.repeat_mode));
          else if (data.repeatMode) dispatch(reduxSetRepeatMode(data.repeatMode));
          break;
      }
    }
  );

  /**
   * Fetch initial queue state on mount
   */
  useEffect(() => {
    const fetchInitialQueue = async () => {
      try {
        const response = await get<Record<string, unknown>>('/api/player/queue');

        if (response) {
          // Backend sends snake_case; map to our state shape
          dispatch(reduxSetQueue((response.tracks as QueueState['tracks']) || []));
          dispatch(reduxSetCurrentIndex(
            (response.current_index as number) ?? (response.currentIndex as number) ?? 0
          ));
          dispatch(reduxSetIsShuffled(
            (response.is_shuffled as boolean) ?? (response.isShuffled as boolean) ?? false
          ));
          dispatch(reduxSetRepeatMode(
            (response.repeat_mode as QueueState['repeatMode']) ?? (response.repeatMode as QueueState['repeatMode']) ?? 'off'
          ));
        }
      } catch (err) {
        // Silently fail - user can still interact with empty queue
        console.warn('Failed to fetch initial queue:', err);
      }
    };

    fetchInitialQueue();
  }, [get, dispatch]);

  /**
   * Set entire queue with optional start index
   *
   * @param tracks Tracks to add to queue
   * @param startIndex Optional index to start playback (default: 0)
   * @throws Error if set queue fails
   */
  const setQueue = useCallback(
    async (tracks: Track[], startIndex: number = 0): Promise<void> => {
      setIsLoading(true);
      setError(null);

      // Optimistic update via Redux
      const previousTracks = stateRef.current.tracks;
      const previousIndex = stateRef.current.currentIndex;

      dispatch(reduxSetQueue(tracks));
      dispatch(reduxSetCurrentIndex(startIndex));

      try {
        // Send to backend
        await post('/api/player/queue', {
          tracks: tracks.map((t) => t.id),
          start_index: startIndex,
        });

        // Server will broadcast confirmation via WebSocket
      } catch (err) {
        // Rollback on error
        dispatch(reduxSetQueue(previousTracks));
        dispatch(reduxSetCurrentIndex(previousIndex));

        const apiError = err instanceof Error
          ? { message: err.message, code: 'QUEUE_SET_ERROR', status: 500 }
          : (err as ApiError);

        setError(apiError);
        throw apiError;
      } finally {
        setIsLoading(false);
      }
    },
    [post, dispatch]
  );

  /**
   * Add single track to queue
   *
   * @param track Track to add
   * @param position Optional position (default: append to end)
   * @throws Error if add fails
   */
  const addTrack = useCallback(
    async (track: Track, position?: number): Promise<void> => {
      setIsLoading(true);
      setError(null);

      try {
        // Add to backend
        await post('/api/player/queue/add-track', {
          track_id: track.id,
          position: position !== undefined ? position : undefined,
        });

        // Server will broadcast confirmation via WebSocket
      } catch (err) {
        const apiError = err instanceof Error
          ? { message: err.message, code: 'ADD_TRACK_ERROR', status: 500 }
          : (err as ApiError);

        setError(apiError);
        throw apiError;
      } finally {
        setIsLoading(false);
      }
    },
    [post]
  );

  /**
   * Remove track at index from queue
   *
   * @param index Index of track to remove
   * @throws Error if remove fails
   */
  const removeTrack = useCallback(
    async (index: number): Promise<void> => {
      setIsLoading(true);
      setError(null);

      try {
        // Remove from backend
        await apiDelete(`/api/player/queue/${index}`);

        // Server will broadcast confirmation via WebSocket
      } catch (err) {
        const apiError = err instanceof Error
          ? { message: err.message, code: 'REMOVE_TRACK_ERROR', status: 500 }
          : (err as ApiError);

        setError(apiError);
        throw apiError;
      } finally {
        setIsLoading(false);
      }
    },
    [apiDelete]
  );

  /**
   * Reorder single track within queue (drag and drop)
   *
   * @param fromIndex Current position
   * @param toIndex Destination position
   * @throws Error if reorder fails
   */
  const reorderTrack = useCallback(
    async (fromIndex: number, toIndex: number): Promise<void> => {
      setIsLoading(true);
      setError(null);

      try {
        // Reorder in backend
        await put('/api/player/queue/reorder', {
          from_index: fromIndex,
          to_index: toIndex,
        });

        // Server will broadcast confirmation via WebSocket
      } catch (err) {
        const apiError = err instanceof Error
          ? { message: err.message, code: 'REORDER_ERROR', status: 500 }
          : (err as ApiError);

        setError(apiError);
        throw apiError;
      } finally {
        setIsLoading(false);
      }
    },
    [put]
  );

  /**
   * Reorder entire queue by specifying new track order
   *
   * @param newOrder Array of track IDs in new order
   * @throws Error if reorder fails
   */
  const reorderQueue = useCallback(
    async (newOrder: number[]): Promise<void> => {
      setIsLoading(true);
      setError(null);

      try {
        // Reorder in backend
        await put('/api/player/queue/reorder', {
          new_order: newOrder,
        });

        // Server will broadcast confirmation via WebSocket
      } catch (err) {
        const apiError = err instanceof Error
          ? { message: err.message, code: 'REORDER_QUEUE_ERROR', status: 500 }
          : (err as ApiError);

        setError(apiError);
        throw apiError;
      } finally {
        setIsLoading(false);
      }
    },
    [put]
  );

  /**
   * Toggle shuffle mode
   *
   * @throws Error if toggle fails
   */
  const toggleShuffle = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);

    // Use ref to get latest state without dependency
    const newShuffle = !stateRef.current.isShuffled;
    const previousShuffle = stateRef.current.isShuffled;

    dispatch(reduxSetIsShuffled(newShuffle));

    try {
      // Send enabled as query param — backend reads it as ?enabled=true/false
      await post('/api/player/queue/shuffle', undefined, {
        enabled: newShuffle,
      });

      // Server will broadcast confirmation via WebSocket
    } catch (err) {
      // Rollback on error
      dispatch(reduxSetIsShuffled(previousShuffle));

      const apiError = err instanceof Error
        ? { message: err.message, code: 'SHUFFLE_ERROR', status: 500 }
        : (err as ApiError);

      setError(apiError);
      throw apiError;
    } finally {
      setIsLoading(false);
    }
  }, [post]);

  /**
   * Set repeat mode
   *
   * @param mode Repeat mode: 'off', 'all', or 'one'
   * @throws Error if set fails
   */
  const setRepeatMode = useCallback(
    async (mode: 'off' | 'all' | 'one'): Promise<void> => {
      setIsLoading(true);
      setError(null);

      // Validate mode
      if (!['off', 'all', 'one'].includes(mode)) {
        const apiError = {
          message: `Invalid repeat mode: ${mode}`,
          code: 'INVALID_REPEAT_MODE',
          status: 400,
        };
        setError(apiError);
        throw apiError;
      }

      // Optimistic update
      const previousMode = stateRef.current.repeatMode;

      dispatch(reduxSetRepeatMode(mode));

      try {
        // Send to backend
        await post('/api/player/queue/repeat', { mode });

        // Server will broadcast confirmation via WebSocket
      } catch (err) {
        // Rollback on error
        dispatch(reduxSetRepeatMode(previousMode));

        const apiError = err instanceof Error
          ? { message: err.message, code: 'REPEAT_MODE_ERROR', status: 500 }
          : (err as ApiError);

        setError(apiError);
        throw apiError;
      } finally {
        setIsLoading(false);
      }
    },
    [post]
  );

  /**
   * Clear entire queue
   *
   * @throws Error if clear fails
   */
  const clearQueue = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);

    // Optimistic update via Redux
    const previousTracks = stateRef.current.tracks;
    const previousIndex = stateRef.current.currentIndex;

    dispatch(reduxClearQueue());

    try {
      // Send to backend
      await post('/api/player/queue/clear');

      // Server will broadcast confirmation via WebSocket
    } catch (err) {
      // Rollback on error
      dispatch(reduxSetQueue(previousTracks));
      dispatch(reduxSetCurrentIndex(previousIndex));

      const apiError = err instanceof Error
        ? { message: err.message, code: 'CLEAR_QUEUE_ERROR', status: 500 }
        : (err as ApiError);

      setError(apiError);
      throw apiError;
    } finally {
      setIsLoading(false);
    }
  }, [post, dispatch]);

  /**
   * Clear error state
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // Memoize return value so object identity is stable when deps haven't changed,
  // preventing cascading re-renders in consumers (fixes #2465).
  return useMemo(() => ({
    state,
    queue: state.tracks,
    currentIndex: state.currentIndex,
    currentTrack,
    isShuffled: state.isShuffled,
    repeatMode: state.repeatMode,
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
    state, currentTrack, isLoading, error,
    setQueue, addTrack, removeTrack, reorderTrack, reorderQueue,
    toggleShuffle, setRepeatMode, clearQueue, clearError,
  ]);
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
