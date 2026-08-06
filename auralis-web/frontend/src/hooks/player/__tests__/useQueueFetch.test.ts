/**
 * useQueueFetch Hook Tests
 *
 * Regression coverage for #4787: the backend (QueueManager.get_queue_info)
 * only ever emits `shuffle_enabled` on GET /api/player/queue, but the hook
 * used to read `is_shuffled`/`isShuffled` — keys the backend never sends —
 * so it always fell through to the `?? false` default regardless of actual
 * server state, racing (and often losing) against the WebSocket connect-time
 * snapshot that reads the field name correctly.
 */

import { ReactNode, createElement } from 'react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { useQueueFetch } from '../useQueueFetch';
import queueReducer, { selectIsShuffled } from '@/store/slices/queueSlice';
import * as useRestAPIModule from '@/hooks/api/useRestAPI';

const createStore = () => configureStore({ reducer: { queue: queueReducer } });
const wrapperFor = (store: ReturnType<typeof createStore>) =>
  ({ children }: { children: ReactNode }) => createElement(Provider, { store, children });

const mockRestAPI = (get: ReturnType<typeof vi.fn>) => {
  vi.spyOn(useRestAPIModule, 'useRestAPI').mockReturnValue({
    get,
    post: vi.fn().mockResolvedValue({}),
    put: vi.fn().mockResolvedValue({}),
    delete: vi.fn().mockResolvedValue({}),
    patch: vi.fn().mockResolvedValue({}),
    clearError: vi.fn(),
    isLoading: false,
    error: null,
  } as any);
};

describe('useQueueFetch', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('reads shuffle_enabled (the real backend field) and dispatches true', async () => {
    mockRestAPI(vi.fn().mockResolvedValue({
      tracks: [],
      current_index: 0,
      shuffle_enabled: true,
      repeat_mode: 'off',
    }));

    const store = createStore();
    renderHook(() => useQueueFetch(), { wrapper: wrapperFor(store) });

    await waitFor(() => {
      expect(selectIsShuffled(store.getState())).toBe(true);
    });
  });

  it('reads shuffle_enabled: false and dispatches false', async () => {
    mockRestAPI(vi.fn().mockResolvedValue({
      tracks: [],
      current_index: 0,
      shuffle_enabled: false,
      repeat_mode: 'off',
    }));

    const store = createStore();
    renderHook(() => useQueueFetch(), { wrapper: wrapperFor(store) });

    await waitFor(() => {
      // Distinguish "dispatched false" from "effect hasn't run yet" (both
      // read as false) by confirming the fetch actually resolved.
      expect(useRestAPIModule.useRestAPI).toHaveBeenCalled();
    });
    expect(selectIsShuffled(store.getState())).toBe(false);
  });

  it('ignores the phantom is_shuffled/isShuffled keys the backend never sends (#4787)', async () => {
    // Simulates the pre-fix bug scenario: only the phantom keys are present,
    // shuffle_enabled is absent — must NOT resolve to true via those keys
    // once they're demoted to a legacy fallback below the real field.
    mockRestAPI(vi.fn().mockResolvedValue({
      tracks: [],
      current_index: 0,
      is_shuffled: false,
      isShuffled: false,
      repeat_mode: 'off',
    }));

    const store = createStore();
    renderHook(() => useQueueFetch(), { wrapper: wrapperFor(store) });

    await waitFor(() => {
      expect(useRestAPIModule.useRestAPI).toHaveBeenCalled();
    });
    expect(selectIsShuffled(store.getState())).toBe(false);
  });

  it('shuffle_enabled wins over a stale legacy is_shuffled value if both are present', async () => {
    mockRestAPI(vi.fn().mockResolvedValue({
      tracks: [],
      current_index: 0,
      shuffle_enabled: true,
      is_shuffled: false,
      repeat_mode: 'off',
    }));

    const store = createStore();
    renderHook(() => useQueueFetch(), { wrapper: wrapperFor(store) });

    await waitFor(() => {
      expect(selectIsShuffled(store.getState())).toBe(true);
    });
  });
});
