/**
 * useQueueMutations.toggleShuffle — request-shape regression tests (#4859)
 *
 * `toggleShuffle` called `post(url, undefined, { enabled })`. The 3rd argument
 * of `useRestAPI.post` is `queryParams`, and a body is only sent when the 2nd
 * argument is truthy — so the request went out as `?enabled=true` with NO JSON
 * body. The backend handler takes a `ShuffleRequest` body (moved query→body in
 * ac3f693a, closing #3174), so FastAPI 422'd every single toggle and the
 * optimistic Redux update was rolled back.
 *
 * These assert the LITERAL argument shape rather than "post was called",
 * because the bug was entirely in which argument the payload landed in — a
 * call-count assertion passes just as happily against the broken version.
 */

import { ReactNode, createElement } from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { useQueueMutations } from '../useQueueMutations';
import queueReducer, { setIsShuffled } from '@/store/slices/queueSlice';
import * as useRestAPIModule from '@/hooks/api/useRestAPI';

let store: ReturnType<typeof configureStore>;
let post: ReturnType<typeof vi.fn>;

const setup = (postImpl?: () => Promise<unknown>) => {
  store = configureStore({ reducer: { queue: queueReducer } });
  post = vi.fn().mockImplementation(postImpl ?? (() => Promise.resolve({})));

  vi.spyOn(useRestAPIModule, 'useRestAPI').mockReturnValue({
    get: vi.fn(),
    post,
    put: vi.fn().mockResolvedValue({}),
    patch: vi.fn(),
    delete: vi.fn().mockResolvedValue({}),
  } as unknown as ReturnType<typeof useRestAPIModule.useRestAPI>);

  const wrapper = ({ children }: { children: ReactNode }) =>
    createElement(Provider, { store, children });

  return renderHook(() => useQueueMutations(), { wrapper });
};

const isShuffled = () => (store.getState() as any).queue.isShuffled;

describe('useQueueMutations.toggleShuffle request shape (#4859)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('sends enabled in the JSON body, not as a query param', async () => {
    const { result } = setup();

    await act(async () => {
      await result.current.toggleShuffle();
    });

    expect(post).toHaveBeenCalledWith('/api/player/queue/shuffle', { enabled: true });
  });

  it('passes no third (queryParams) argument at all', async () => {
    const { result } = setup();

    await act(async () => {
      await result.current.toggleShuffle();
    });

    // The precise regression: `enabled` must not travel as queryParams.
    const [, payload, queryParams] = post.mock.calls[0];
    expect(payload).toEqual({ enabled: true });
    expect(queryParams).toBeUndefined();
  });

  it('sends enabled:false when toggling shuffle back off', async () => {
    const { result } = setup();
    act(() => {
      store.dispatch(setIsShuffled(true));
    });

    await act(async () => {
      await result.current.toggleShuffle();
    });

    expect(post).toHaveBeenCalledWith('/api/player/queue/shuffle', { enabled: false });
  });

  it('keeps the optimistic state when the request succeeds', async () => {
    const { result } = setup();
    expect(isShuffled()).toBe(false);

    await act(async () => {
      await result.current.toggleShuffle();
    });

    expect(isShuffled()).toBe(true);
  });

  it('rolls back and rethrows when the request fails', async () => {
    const { result } = setup(() => Promise.reject(new Error('HTTP 422: Unprocessable Entity')));

    await act(async () => {
      await expect(result.current.toggleShuffle()).rejects.toBeDefined();
    });

    // This is what the user saw on every toggle before the fix.
    expect(isShuffled()).toBe(false);
  });
});
