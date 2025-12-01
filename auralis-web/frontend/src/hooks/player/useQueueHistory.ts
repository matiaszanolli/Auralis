/**
 * useQueueHistory Hook
 * ~~~~~~~~~~~~~~~~~~~~
 *
 * Provides undo/redo functionality for queue operations.
 * Manages history state, undo/redo actions, and integrates with queue management.
 *
 * Usage:
 * ```typescript
 * const {
 *   historyCount,
 *   canUndo,
 *   canRedo,
 *   undo,
 *   redo,
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
 * - Track queue state changes for undo/redo
 * - Record operation metadata (what changed)
 * - Limit history to 20 entries for memory efficiency
 * - Integrate with queue state management
 * - Error handling and recovery
 * - History persistence across app restarts
 *
 * @module hooks/player/useQueueHistory
 */

import { useCallback, useState, useEffect } from 'react';
import { useRestAPI } from '@/hooks/api/useRestAPI';
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
  metadata: Record<string, any>;

  /** When operation was recorded */
  createdAt: string;
}

/**
 * Return type for useQueueHistory hook
 */
export interface QueueHistoryActions {
  /** Number of history entries available */
  historyCount: number;

  /** Whether undo is available */
  canUndo: boolean;

  /** Whether redo is available (future: when redo implemented) */
  canRedo: boolean;

  /** History entries (newest first) */
  history: HistoryEntry[];

  /** Record a queue operation to history */
  recordOperation: (
    operation: 'set' | 'add' | 'remove' | 'reorder' | 'shuffle' | 'clear',
    stateSnapshot: HistoryEntry['stateSnapshot'],
    metadata?: Record<string, any>
  ) => Promise<void>;

  /** Undo the last queue operation */
  undo: () => Promise<void>;

  /** Redo (not yet implemented) */
  redo: () => Promise<void>;

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
 * Hook for managing queue undo/redo history
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
  const api = useRestAPI();

  // Local state
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [historyCount, setHistoryCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  /**
   * Fetch initial history on mount
   */
  useEffect(() => {
    const fetchInitialHistory = async () => {
      try {
        const response = await api.get<{
          history: HistoryEntry[];
          count: number;
        }>('/api/player/queue/history');

        if (response) {
          setHistory(response.history || []);
          setHistoryCount(response.count || 0);
        }
      } catch (err) {
        // Silently fail - history is optional
        console.warn('Failed to fetch queue history:', err);
      }
    };

    fetchInitialHistory();
  }, [api]);

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
      metadata?: Record<string, any>
    ): Promise<void> => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await api.post<HistoryEntry>(
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

        if (response) {
          // Update local history
          setHistory((prev) => [response, ...prev]);
          setHistoryCount((prev) => prev + 1);
        }

        setIsLoading(false);
      } catch (err) {
        const apiError = err as ApiError;
        setError(apiError);
        setIsLoading(false);
        throw err;
      }
    },
    [api]
  );

  /**
   * Undo the last queue operation
   *
   * @throws Error if undo fails or no history available
   */
  const undo = useCallback(async (): Promise<void> => {
    if (!canUndo) {
      throw new Error('No history available to undo');
    }

    setIsLoading(true);
    setError(null);

    try {
      // Call undo endpoint
      await api.post('/api/player/queue/undo', {});

      // Remove the undone entry from local history
      setHistory((prev) => prev.slice(1));
      setHistoryCount((prev) => Math.max(0, prev - 1));

      setIsLoading(false);
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError);
      setIsLoading(false);
      throw err;
    }
  }, [api, canUndo]);

  /**
   * Redo (not yet implemented)
   *
   * @throws Error indicating redo not implemented
   */
  const redo = useCallback(async (): Promise<void> => {
    throw new Error('Redo not yet implemented');
  }, []);

  /**
   * Clear all history
   *
   * @throws Error if clear fails
   */
  const clearHistory = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);

    try {
      await api.delete('/api/player/queue/history');

      setHistory([]);
      setHistoryCount(0);

      setIsLoading(false);
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError);
      setIsLoading(false);
      throw err;
    }
  }, [api]);

  /**
   * Clear error state
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    historyCount,
    canUndo: history.length > 0,
    canRedo: false, // Not yet implemented
    history,
    recordOperation,
    undo,
    redo,
    clearHistory,
    isLoading,
    error,
    clearError,
  };
}
