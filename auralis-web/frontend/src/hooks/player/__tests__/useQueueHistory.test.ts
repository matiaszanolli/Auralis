/**
 * useQueueHistory Hook Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Runtime behavior tests for queue history undo/redo functionality.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useQueueHistory } from '../useQueueHistory';
import type { HistoryEntry } from '../useQueueHistory';

// Mock REST API
const mockGet = vi.fn();
const mockPost = vi.fn();
const mockDelete = vi.fn();

vi.mock('@/hooks/api/useRestAPI', () => ({
  useRestAPI: () => ({
    get: mockGet,
    post: mockPost,
    put: vi.fn(),
    patch: vi.fn(),
    delete: mockDelete,
    clearError: vi.fn(),
    isLoading: false,
    error: null,
  }),
}));

const makeEntry = (id: number, operation: HistoryEntry['operation'] = 'add'): HistoryEntry => ({
  id,
  operation,
  stateSnapshot: {
    trackIds: [1, 2, 3],
    currentIndex: 0,
    isShuffled: false,
    repeatMode: 'off',
  },
  metadata: {},
  createdAt: new Date().toISOString(),
});

describe('useQueueHistory', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: initial fetch returns empty history
    mockGet.mockResolvedValue({ history: [], count: 0 });
  });

  it('should return initial state with empty history', async () => {
    const { result } = renderHook(() => useQueueHistory());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.historyCount).toBe(0);
    expect(result.current.canUndo).toBe(false);
    expect(result.current.canRedo).toBe(false);
    expect(result.current.history).toEqual([]);
    expect(result.current.error).toBeNull();
  });

  it('should load initial history from API on mount', async () => {
    const entries = [makeEntry(1), makeEntry(2)];
    mockGet.mockResolvedValue({ history: entries, count: 2 });

    const { result } = renderHook(() => useQueueHistory());

    await waitFor(() => expect(result.current.historyCount).toBe(2));

    expect(result.current.history).toEqual(entries);
    expect(result.current.canUndo).toBe(true);
  });

  describe('recordOperation', () => {
    it('should add entry to history on success', async () => {
      const newEntry = makeEntry(10, 'add');
      mockPost.mockResolvedValue(newEntry);

      const { result } = renderHook(() => useQueueHistory());
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      await act(async () => {
        await result.current.recordOperation('add', {
          trackIds: [1, 2, 3],
          currentIndex: 0,
          isShuffled: false,
          repeatMode: 'off',
        });
      });

      expect(result.current.history[0]).toEqual(newEntry);
      expect(result.current.historyCount).toBe(1);
      expect(result.current.canUndo).toBe(true);
    });

    it('should set error state on failure', async () => {
      const apiError = { message: 'Server error', code: 'ERR', status: 500 };
      mockPost.mockRejectedValue(apiError);

      const { result } = renderHook(() => useQueueHistory());
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      let thrown = false;
      await act(async () => {
        try {
          await result.current.recordOperation('add', {
            trackIds: [],
            currentIndex: 0,
            isShuffled: false,
            repeatMode: 'off',
          });
        } catch {
          thrown = true;
        }
      });

      expect(thrown).toBe(true);
      expect(result.current.error).toEqual(apiError);
    });
  });

  describe('undo', () => {
    it('should remove first entry from history on success', async () => {
      const entries = [makeEntry(2, 'add'), makeEntry(1, 'set')];
      mockGet.mockResolvedValue({ history: entries, count: 2 });
      mockPost.mockResolvedValue({});

      const { result } = renderHook(() => useQueueHistory());
      await waitFor(() => expect(result.current.historyCount).toBe(2));

      await act(async () => {
        await result.current.undo();
      });

      expect(result.current.history).toHaveLength(1);
      expect(result.current.history[0].id).toBe(1);
      expect(result.current.historyCount).toBe(1);
    });

    it('should throw when no history available', async () => {
      const { result } = renderHook(() => useQueueHistory());
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      await expect(
        act(async () => {
          await result.current.undo();
        })
      ).rejects.toThrow('No history available to undo');
    });
  });

  describe('redo', () => {
    it('should throw not implemented error', async () => {
      const { result } = renderHook(() => useQueueHistory());
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      await expect(
        act(async () => {
          await result.current.redo();
        })
      ).rejects.toThrow('Redo not yet implemented');
    });
  });

  describe('clearHistory', () => {
    it('should clear all history on success', async () => {
      const entries = [makeEntry(1), makeEntry(2)];
      mockGet.mockResolvedValue({ history: entries, count: 2 });
      mockDelete.mockResolvedValue({});

      const { result } = renderHook(() => useQueueHistory());
      await waitFor(() => expect(result.current.historyCount).toBe(2));

      await act(async () => {
        await result.current.clearHistory();
      });

      expect(result.current.history).toEqual([]);
      expect(result.current.historyCount).toBe(0);
      expect(result.current.canUndo).toBe(false);
    });
  });

  describe('isLoading reset on failure (#3399 regression)', () => {
    // Pre-fix: setIsLoading(false) was duplicated in both try and catch
    // branches; any divergence between them (or a future maintainer adding
    // a setter that throws before the catch's reset ran) would leave
    // isLoading stuck at true. Post-fix it lives in a single `finally`.

    it('recordOperation: isLoading returns to false after API failure', async () => {
      mockPost.mockRejectedValue({ message: 'fail', status: 500 });
      const { result } = renderHook(() => useQueueHistory());
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      await act(async () => {
        try {
          await result.current.recordOperation('add', {
            trackIds: [], currentIndex: 0, isShuffled: false, repeatMode: 'off',
          });
        } catch { /* expected */ }
      });

      expect(result.current.isLoading).toBe(false);
    });

    it('undo: isLoading returns to false after API failure', async () => {
      const entries = [makeEntry(1, 'add')];
      mockGet.mockResolvedValue({ history: entries, count: 1 });
      mockPost.mockRejectedValue({ message: 'fail', status: 500 });

      const { result } = renderHook(() => useQueueHistory());
      await waitFor(() => expect(result.current.historyCount).toBe(1));

      await act(async () => {
        try { await result.current.undo(); } catch { /* expected */ }
      });

      expect(result.current.isLoading).toBe(false);
    });

    it('clearHistory: isLoading returns to false after API failure', async () => {
      mockDelete.mockRejectedValue({ message: 'fail', status: 500 });
      const { result } = renderHook(() => useQueueHistory());
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      await act(async () => {
        try { await result.current.clearHistory(); } catch { /* expected */ }
      });

      expect(result.current.isLoading).toBe(false);
    });

    it('isLoading also resets on success (smoke check)', async () => {
      mockPost.mockResolvedValue(makeEntry(1));
      const { result } = renderHook(() => useQueueHistory());
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      await act(async () => {
        await result.current.recordOperation('add', {
          trackIds: [], currentIndex: 0, isShuffled: false, repeatMode: 'off',
        });
      });

      expect(result.current.isLoading).toBe(false);
    });
  });

  describe('clearError', () => {
    it('should reset error to null', async () => {
      mockPost.mockRejectedValue({ message: 'fail', status: 500 });

      const { result } = renderHook(() => useQueueHistory());
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      // Trigger an error
      await act(async () => {
        try {
          await result.current.recordOperation('add', {
            trackIds: [],
            currentIndex: 0,
            isShuffled: false,
            repeatMode: 'off',
          });
        } catch { /* expected */ }
      });

      expect(result.current.error).toBeTruthy();

      act(() => {
        result.current.clearError();
      });

      expect(result.current.error).toBeNull();
    });
  });
});
