/**
 * The initial queue read survives a backend that is still starting (#5655).
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { createElement, type ReactNode } from 'react';
import { Provider } from 'react-redux';
import { renderHook, waitFor } from '@testing-library/react';
import { useQueueFetch } from '../useQueueFetch';
import { createTestStore } from '@/test/test-utils';
import { APIRequestError } from '@/utils/apiRequest';
import * as useRestAPIModule from '@/hooks/api/useRestAPI';

function mockGet(get: ReturnType<typeof vi.fn>) {
  vi.spyOn(useRestAPIModule, 'useRestAPI').mockReturnValue({
    get, post: vi.fn(), put: vi.fn(), delete: vi.fn(), patch: vi.fn(),
    clearError: vi.fn(), isLoading: false, error: null,
  } as never);
}

const wrapperFor = (store: ReturnType<typeof createTestStore>) =>
  ({ children }: { children: ReactNode }) => createElement(Provider, { store, children });

describe('useQueueFetch retry (#5655)', () => {
  afterEach(() => vi.restoreAllMocks());

  it('seeds the queue after a transient failure instead of keeping the empty default', async () => {
    const queue = {
      tracks: [{ id: 1, title: 'A', artist: 'X', album: 'Al', duration: 180 }],
      current_index: 0, shuffle_enabled: false, repeat_mode: 'off',
    };
    const get = vi.fn()
      .mockRejectedValueOnce(new APIRequestError('Network error: backend starting', 0))
      .mockResolvedValue(queue);
    mockGet(get);
    const store = createTestStore();

    renderHook(() => useQueueFetch(), { wrapper: wrapperFor(store) });

    await waitFor(() => expect(store.getState().queue.tracks).toHaveLength(1), { timeout: 3000 });
    expect(get).toHaveBeenCalledTimes(2);
  });

  it('does not retry a request the backend rejected', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const get = vi.fn().mockRejectedValue(new APIRequestError('bad request', 400));
    mockGet(get);

    renderHook(() => useQueueFetch(), { wrapper: wrapperFor(createTestStore()) });

    await waitFor(() => expect(warn).toHaveBeenCalled());
    expect(get).toHaveBeenCalledTimes(1);
  });
});
