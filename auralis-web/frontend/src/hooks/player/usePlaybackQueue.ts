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

import { useCallback, useState, useEffect } from 'react';
import { useRestAPI } from '@/hooks/api/useRestAPI';
import { useWebSocketSubscription } from '@/hooks/websocket/useWebSocketSubscription';
import type { Track } from '@/types/domain';
import type { ApiError } from '@/types/api';

/**
 * Queue state and metadata
 */
export interface QueueState {
  /** Tracks in queue */
  tracks: Track[];

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
  queue: Track[];

  /** Current queue index */
  currentIndex: number;

  /** Current track in queue (or null) */
  currentTrack: Track | null;

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
 * Initial queue state
 */
const INITIAL_STATE: QueueState = {
  tracks: [],
  currentIndex: 0,
  isShuffled: false,
  repeatMode: 'off',
  lastUpdated: Date.now(),
};

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
  const api = useRestAPI();

  // Local state
  const [state, setState] = useState<QueueState>(INITIAL_STATE);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  /**
   * Subscribe to real-time queue updates via WebSocket
   */
  useWebSocketSubscription(
    ['queue_changed', 'queue_shuffled', 'repeat_mode_changed'],
    (message) => {
      const { type, data } = message as any;

      setState((prevState) => {
        switch (type) {
          case 'queue_changed':
            return {
              ...prevState,
              tracks: data.tracks || prevState.tracks,
              currentIndex: data.currentIndex ?? prevState.currentIndex,
              lastUpdated: Date.now(),
            };

          case 'queue_shuffled':
            return {
              ...prevState,
              isShuffled: data.isShuffled ?? prevState.isShuffled,
              tracks: data.tracks || prevState.tracks,
              lastUpdated: Date.now(),
            };

          case 'repeat_mode_changed':
            return {
              ...prevState,
              repeatMode: data.repeatMode ?? prevState.repeatMode,
              lastUpdated: Date.now(),
            };

          default:
            return prevState;
        }
      });
    }
  );

  /**
   * Fetch initial queue state on mount
   */
  useEffect(() => {
    const fetchInitialQueue = async () => {
      try {
        const response = await api.get<QueueState>('/api/player/queue');

        if (response) {
          setState({
            tracks: response.tracks || [],
            currentIndex: response.currentIndex ?? 0,
            isShuffled: response.isShuffled ?? false,
            repeatMode: response.repeatMode ?? 'off',
            lastUpdated: Date.now(),
          });
        }
      } catch (err) {
        // Silently fail - user can still interact with empty queue
        console.warn('Failed to fetch initial queue:', err);
      }
    };

    fetchInitialQueue();
  }, [api]);

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

      // Optimistic update
      const previousState = state;

      setState({
        tracks,
        currentIndex: startIndex,
        isShuffled: state.isShuffled,
        repeatMode: state.repeatMode,
        lastUpdated: Date.now(),
      });

      try {
        // Send to backend
        await api.post('/api/player/queue', {
          tracks: tracks.map((t) => t.id),
          start_index: startIndex,
        });

        // Server will broadcast confirmation via WebSocket
      } catch (err) {
        // Rollback on error
        setState(previousState);

        const apiError = err instanceof Error
          ? { message: err.message, code: 'QUEUE_SET_ERROR', status: 500 }
          : (err as ApiError);

        setError(apiError);
        throw apiError;
      } finally {
        setIsLoading(false);
      }
    },
    [api, state]
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
        await api.post('/api/player/queue/add', {
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
    [api]
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
        await api.delete(`/api/player/queue/${index}`);

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
    [api]
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
        await api.put('/api/player/queue/reorder', {
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
    [api]
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
        await api.put('/api/player/queue/reorder', {
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
    [api]
  );

  /**
   * Toggle shuffle mode
   *
   * @throws Error if toggle fails
   */
  const toggleShuffle = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);

    const newShuffle = !state.isShuffled;

    // Optimistic update
    const previousState = state;

    setState((prevState) => ({
      ...prevState,
      isShuffled: newShuffle,
      lastUpdated: Date.now(),
    }));

    try {
      // Send to backend
      await api.post('/api/player/queue/shuffle', undefined, {
        enabled: newShuffle,
      });

      // Server will broadcast confirmation via WebSocket
    } catch (err) {
      // Rollback on error
      setState(previousState);

      const apiError = err instanceof Error
        ? { message: err.message, code: 'SHUFFLE_ERROR', status: 500 }
        : (err as ApiError);

      setError(apiError);
      throw apiError;
    } finally {
      setIsLoading(false);
    }
  }, [api, state.isShuffled]);

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
      const previousState = state;

      setState((prevState) => ({
        ...prevState,
        repeatMode: mode,
        lastUpdated: Date.now(),
      }));

      try {
        // Send to backend
        await api.post('/api/player/queue/repeat', undefined, {
          mode,
        });

        // Server will broadcast confirmation via WebSocket
      } catch (err) {
        // Rollback on error
        setState(previousState);

        const apiError = err instanceof Error
          ? { message: err.message, code: 'REPEAT_MODE_ERROR', status: 500 }
          : (err as ApiError);

        setError(apiError);
        throw apiError;
      } finally {
        setIsLoading(false);
      }
    },
    [api, state]
  );

  /**
   * Clear entire queue
   *
   * @throws Error if clear fails
   */
  const clearQueue = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);

    // Optimistic update
    const previousState = state;

    setState({
      tracks: [],
      currentIndex: 0,
      isShuffled: state.isShuffled,
      repeatMode: state.repeatMode,
      lastUpdated: Date.now(),
    });

    try {
      // Send to backend
      await api.post('/api/player/queue/clear');

      // Server will broadcast confirmation via WebSocket
    } catch (err) {
      // Rollback on error
      setState(previousState);

      const apiError = err instanceof Error
        ? { message: err.message, code: 'CLEAR_QUEUE_ERROR', status: 500 }
        : (err as ApiError);

      setError(apiError);
      throw apiError;
    } finally {
      setIsLoading(false);
    }
  }, [api, state]);

  /**
   * Clear error state
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // Get current track from queue
  const currentTrack = state.tracks[state.currentIndex] || null;

  return {
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
  };
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
