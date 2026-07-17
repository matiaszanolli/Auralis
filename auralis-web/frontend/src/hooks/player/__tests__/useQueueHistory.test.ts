/**
 * useQueueHistory Hook Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Runtime behavior tests for queue history undo functionality.
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

/** Wire-format (snake_case) fixture — matches the actual backend response
 * shape (routers/player.py's QueueHistoryEntryResponse, #3805). The hook
 * maps this into the camelCase HistoryEntry the rest of the app consumes. */
const makeWireEntry = (id: number, operation: HistoryEntry['operation'] = 'add') => ({
  id,
  operation,
  state_snapshot: {
    track_ids: [1, 2, 3],
    current_index: 0,
    is_shuffled: false,
    repeat_mode: 'off' as const,
  },
  operation_metadata: {},
  created_at: new Date().toISOString(),
});

const expectedEntry = (wire: ReturnType<typeof makeWireEntry>): HistoryEntry => ({
  id: wire.id,
  operation: wire.operation,
  stateSnapshot: {
    trackIds: wire.state_snapshot.track_ids,
    currentIndex: wire.state_snapshot.current_index,
    isShuffled: wire.state_snapshot.is_shuffled,
    repeatMode: wire.state_snapshot.repeat_mode,
  },
  metadata: wire.operation_metadata,
  createdAt: wire.created_at,
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
    expect(result.current.history).toEqual([]);
    expect(result.current.error).toBeNull();
  });

  it('should load initial history from API on mount, mapping snake_case to camelCase (#3805)', async () => {
    const wireEntries = [makeWireEntry(1), makeWireEntry(2)];
    mockGet.mockResolvedValue({ history: wireEntries, count: 2 });

    const { result } = renderHook(() => useQueueHistory());

    await waitFor(() => expect(result.current.historyCount).toBe(2));

    expect(result.current.history).toEqual(wireEntries.map(expectedEntry));
    expect(result.current.canUndo).toBe(true);
  });

  it('does not update state from a stale initial-fetch response after unmount (fixes #3925)', async () => {
    let resolveGet: (value: unknown) => void = () => {};
    const pending = new Promise((resolve) => {
      resolveGet = resolve;
    });
    mockGet.mockReturnValue(pending);

    // React logs "Can't perform a React state update on an unmounted
    // component" via console.error when a stale setState slips through an
    // unmount guard — the signal this test relies on.
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const { unmount } = renderHook(() => useQueueHistory());

    // Unmount before the in-flight GET resolves — simulates React 18 Strict
    // Mode's mount->cleanup->remount, or a fast navigation away from the page.
    unmount();

    await act(async () => {
      resolveGet({ history: [makeWireEntry(1)], count: 1 });
      await pending;
    });

    const unmountedUpdateWarning = consoleErrorSpy.mock.calls.some((call) =>
      String(call[0]).includes("Can't perform a React state update on an unmounted component")
    );
    expect(unmountedUpdateWarning).toBe(false);

    consoleErrorSpy.mockRestore();
  });

  describe('recordOperation', () => {
    it('should add entry to history on success, mapping the wire response', async () => {
      const wireEntry = makeWireEntry(10, 'add');
      mockPost.mockResolvedValue(wireEntry);

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

      expect(result.current.history[0]).toEqual(expectedEntry(wireEntry));
      expect(result.current.historyCount).toBe(1);
      expect(result.current.canUndo).toBe(true);
    });

    it('should send snake_case field names in the request body', async () => {
      mockPost.mockResolvedValue(makeWireEntry(1));
      const { result } = renderHook(() => useQueueHistory());
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      await act(async () => {
        await result.current.recordOperation('shuffle', {
          trackIds: [4, 5],
          currentIndex: 1,
          isShuffled: true,
          repeatMode: 'all',
        }, { note: 'test' });
      });

      expect(mockPost).toHaveBeenCalledWith('/api/player/queue/history', {
        operation: 'shuffle',
        state_snapshot: {
          track_ids: [4, 5],
          current_index: 1,
          is_shuffled: true,
          repeat_mode: 'all',
        },
        operation_metadata: { note: 'test' },
      });
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
      const wireEntries = [makeWireEntry(2, 'add'), makeWireEntry(1, 'set')];
      mockGet.mockResolvedValue({ history: wireEntries, count: 2 });
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

  describe('clearHistory', () => {
    it('should clear all history on success', async () => {
      const wireEntries = [makeWireEntry(1), makeWireEntry(2)];
      mockGet.mockResolvedValue({ history: wireEntries, count: 2 });
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
      const wireEntries = [makeWireEntry(1, 'add')];
      mockGet.mockResolvedValue({ history: wireEntries, count: 1 });
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
      mockPost.mockResolvedValue(makeWireEntry(1));
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
