/**
 * useQueueHistory Hook
 * ~~~~~~~~~~~~~~~~~~~~
 *
 * Provides undo functionality for queue operations.
 * Manages history state, the undo action, and integrates with queue management.
 *
 * Usage:
 * ```typescript
 * const {
 *   historyCount,
 *   canUndo,
 *   undo,
 *   clearHistory,
 *   isLoading,
 *   error
 * } = useQueueHistory();
 *
 * // Record operation
 * await recordOperation('add', { track_id: 5 });
 *
 * // Undo last operation
 * await undo();
 * ```
 *
 * Features:
 * - Track queue state changes for undo
 * - Record operation metadata (what changed)
 * - Limit history to 20 entries for memory efficiency
 * - Integrate with queue state management
 * - Error handling and recovery
 * - History persistence across app restarts
 *
 * @module hooks/player/useQueueHistory
 */

import { useCallback, useState, useEffect, useRef } from 'react';
import { useRestAPI } from '@/hooks/api/useRestAPI';
import { isApiError,
  ApiErrorHandler,
} from '@/types/api';
import type { ApiError } from '@/types/api';

/**
 * History entry representing a queue operation
 */
export interface HistoryEntry {
  /** Entry ID */
  id: number;

  /** Type of operation: 'set', 'add', 'remove', 'reorder', 'shuffle', 'clear' */
  operation: 'set' | 'add' | 'remove' | 'reorder' | 'shuffle' | 'clear';

  /** Queue state snapshot before the operation */
  stateSnapshot: {
    trackIds: number[];
    currentIndex: number;
    isShuffled: boolean;
    repeatMode: 'off' | 'all' | 'one';
  };

  /** Operation-specific metadata */
  metadata: Record<string, unknown>;

  /** When operation was recorded */
  createdAt: string;
}

/** Wire shape returned by the backend (snake_case, matches routers/player.py's
 * QueueHistoryEntryResponse — no automatic case conversion happens in
 * useRestAPI, #3805). */
interface WireHistoryEntry {
  id: number;
  operation: HistoryEntry['operation'];
  state_snapshot: {
    track_ids: number[];
    current_index: number;
    is_shuffled: boolean;
    repeat_mode: HistoryEntry['stateSnapshot']['repeatMode'];
  };
  operation_metadata: Record<string, unknown>;
  created_at: string | null;
}

function mapWireEntry(wire: WireHistoryEntry): HistoryEntry {
  return {
    id: wire.id,
    operation: wire.operation,
    stateSnapshot: {
      trackIds: wire.state_snapshot?.track_ids ?? [],
      currentIndex: wire.state_snapshot?.current_index ?? 0,
      isShuffled: wire.state_snapshot?.is_shuffled ?? false,
      repeatMode: wire.state_snapshot?.repeat_mode ?? 'off',
    },
    metadata: wire.operation_metadata ?? {},
    createdAt: wire.created_at ?? '',
  };
}

/**
 * Return type for useQueueHistory hook
 */
export interface QueueHistoryActions {
  /** Number of history entries available */
  historyCount: number;

  /** Whether undo is available */
  canUndo: boolean;

  /** History entries (newest first) */
  history: HistoryEntry[];

  /** Record a queue operation to history */
  recordOperation: (
    operation: 'set' | 'add' | 'remove' | 'reorder' | 'shuffle' | 'clear',
    stateSnapshot: HistoryEntry['stateSnapshot'],
    metadata?: Record<string, unknown>
  ) => Promise<void>;

  /** Undo the last queue operation */
  undo: () => Promise<void>;

  /** Clear all history */
  clearHistory: () => Promise<void>;

  /** True while a command is executing */
  isLoading: boolean;

  /** Last error from a command */
  error: ApiError | null;

  /** Clear error state */
  clearError: () => void;
}

/**
 * Hook for managing queue undo history
 *
 * @returns Queue history management actions and state
 *
 * @example
 * ```typescript
 * const { historyCount, canUndo, undo, recordOperation } = useQueueHistory();
 *
 * // Record that we added a track (before the actual operation)
 * await recordOperation('add', currentQueueState, { trackId: 5 });
 *
 * // Undo if operation is available
 * if (canUndo) {
 *   await undo();
 * }
 * ```
 */
export function useQueueHistory(): QueueHistoryActions {
  const { get, post, delete: apiDelete } = useRestAPI();

  // Local state
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const historyCount = history.length;
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  // Ref for stable callback access to history
  const historyRef = useRef(history);
  historyRef.current = history;

  // Guard against setState after unmount (#3253)
  const isMountedRef = useRef(true);
  useEffect(() => {
    return () => { isMountedRef.current = false; };
  }, []);

  /**
   * Fetch initial history on mount
   *
   * Gated on a per-effect `isActive` flag in addition to `isMountedRef`
   * (fixes #3925): `isMountedRef` only ever flips true->false once and is
   * never reset, so it can't by itself protect against React 18 Strict
   * Mode's mount->cleanup->remount double-invoke, where two overlapping
   * requests fire and the stale one can resolve after — and overwrite —
   * the fresh one. `isActive` is scoped per effect run, so each duplicate
   * invocation gets its own flag.
   */
  useEffect(() => {
    let isActive = true;

    const fetchInitialHistory = async () => {
      try {
        const response = await get<{
          history: WireHistoryEntry[];
          count: number;
        }>('/api/player/queue/history');

        if (isMountedRef.current && isActive && response) {
          setHistory((response.history || []).map(mapWireEntry));
        }
      } catch (err) {
        // Silently fail - history is optional
        console.warn('Failed to fetch queue history:', err);
      }
    };

    fetchInitialHistory();

    return () => {
      isActive = false;
    };
  }, [get]);

  /**
   * Record a queue operation to history
   *
   * @param operation Type of operation
   * @param stateSnapshot Queue state before operation
   * @param metadata Optional operation metadata
   * @throws Error if recording fails
   */
  const recordOperation = useCallback(
    async (
      operation: 'set' | 'add' | 'remove' | 'reorder' | 'shuffle' | 'clear',
      stateSnapshot: HistoryEntry['stateSnapshot'],
      metadata?: Record<string, unknown>
    ): Promise<void> => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await post<WireHistoryEntry>(
          '/api/player/queue/history',
          {
            operation,
            state_snapshot: {
              track_ids: stateSnapshot.trackIds,
              current_index: stateSnapshot.currentIndex,
              is_shuffled: stateSnapshot.isShuffled,
              repeat_mode: stateSnapshot.repeatMode,
            },
            operation_metadata: metadata || {},
          }
        );

        if (isMountedRef.current && response) {
          // Update local history
          setHistory((prev) => [mapWireEntry(response), ...prev]);
        }
      } catch (err) {
        if (isMountedRef.current) {
          const apiError: ApiError = isApiError(err)
            ? err
            : { status: 0, message: err instanceof Error ? err.message : 'Unknown error' };
          setError(apiError);
        }
        throw err;
      } finally {
        // Always reset loading state — single source of truth (#3399).
        if (isMountedRef.current) setIsLoading(false);
      }
    },
    [post]
  );

  /**
   * Undo the last queue operation
   *
   * @throws Error if undo fails or no history available
   */
  const undo = useCallback(async (): Promise<void> => {
    if (historyRef.current.length === 0) {
      throw new Error('No history available to undo');
    }

    setIsLoading(true);
    setError(null);

    try {
      // Call undo endpoint
      await post('/api/player/queue/undo', {});

      if (isMountedRef.current) {
        // Remove the undone entry from local history
        setHistory((prev) => prev.slice(1));
      }
    } catch (err) {
      if (isMountedRef.current) {
        const apiError = ApiErrorHandler.parse(err);
        setError(apiError);
      }
      throw err;
    } finally {
      // Always reset loading state — single source of truth (#3399).
      if (isMountedRef.current) setIsLoading(false);
    }
  }, [post]);

  /**
   * Clear all history
   *
   * @throws Error if clear fails
   */
  const clearHistory = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);

    try {
      await apiDelete('/api/player/queue/history');

      if (isMountedRef.current) {
        setHistory([]);
      }
    } catch (err) {
      if (isMountedRef.current) {
        const apiError = ApiErrorHandler.parse(err);
        setError(apiError);
      }
      throw err;
    } finally {
      // Always reset loading state — single source of truth (#3399).
      if (isMountedRef.current) setIsLoading(false);
    }
  }, [apiDelete]);

  /**
   * Clear error state
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    historyCount,
    canUndo: history.length > 0,
    history,
    recordOperation,
    undo,
    clearHistory,
    isLoading,
    error,
    clearError,
  };
}
