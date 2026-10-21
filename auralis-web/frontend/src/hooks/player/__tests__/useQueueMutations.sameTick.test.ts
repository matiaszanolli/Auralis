/**
 * useQueueMutations — same-tick snapshot and shared isLoading (#5624)
 *
 * The optimistic-rollback snapshot used to come from a render-time ref: two
 * mutations started in the same tick both captured the pre-FIRST-mutation
 * state, so when the newest one failed it rolled back past the earlier
 * mutation's already-applied result. Snapshots now read the store at call
 * time, seeing every optimistically-applied predecessor. isLoading was one
 * shared boolean cleared by whichever mutation finished first; it is now an
 * in-flight count that only drops when every mutation has settled.
 */

import { ReactNode, createElement } from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { useQueueMutations } from '../useQueueMutations';
import queueReducer, { setQueue as reduxSetQueue } from '@/store/slices/queueSlice';
import * as useRestAPIModule from '@/hooks/api/useRestAPI';
import type { Track } from '@/types/domain';

const track = (id: number): Track => ({
  id,
  title: `Track ${id}`,
  artist: `Artist ${id}`,
  album: `Album ${id}`,
  duration: 100 + id,
});

const seed = [track(1), track(2), track(3)];

function deferred<T = unknown>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

let store: ReturnType<typeof configureStore>;

type RequestFn = (...args: unknown[]) => Promise<unknown>;

const setup = (rest: Partial<Record<'post' | 'put' | 'delete', RequestFn>>) => {
  store = configureStore({ reducer: { queue: queueReducer } });
  store.dispatch(reduxSetQueue(seed));

  vi.spyOn(useRestAPIModule, 'useRestAPI').mockReturnValue({
    get: vi.fn(),
    post: vi.fn().mockImplementation(rest.post ?? (() => Promise.resolve({}))),
    put: vi.fn().mockImplementation(rest.put ?? (() => Promise.resolve({}))),
    patch: vi.fn(),
    delete: vi.fn().mockImplementation(rest.delete ?? (() => Promise.resolve({}))),
  } as unknown as ReturnType<typeof useRestAPIModule.useRestAPI>);

  const wrapper = ({ children }: { children: ReactNode }) =>
    createElement(Provider, { store, children });

  return renderHook(() => useQueueMutations(), { wrapper });
};

const ids = () =>
  (store.getState() as { queue: { tracks: Track[] } }).queue.tracks.map((t) => t.id);

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('useQueueMutations same-tick snapshots and loading counter (#5624)', () => {
  it('a failed second same-tick mutation rolls back only to the first mutation’s result', async () => {
    // Both requests hang until settled; the first resolves, the second rejects.
    const first = deferred();
    const second = deferred();
    const { result } = setup({
      post: vi.fn().mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise),
    });

    let firstCall!: Promise<void>;
    let secondCall!: Promise<void>;
    // Both mutations start in the same tick, before React re-renders —
    // exactly the case the render-time ref got wrong.
    act(() => {
      firstCall = result.current.addTrack(track(9));
      secondCall = result.current.addTrack(track(8));
    });
    expect(ids()).toEqual([1, 2, 3, 9, 8]);

    await act(async () => {
      first.resolve({});
    });
    await act(async () => {
      second.reject(new Error('network'));
    });
    await expect(secondCall).rejects.toThrow('network');
    await firstCall;

    // The old ref-based snapshot rolled back to [1, 2, 3], discarding the
    // first (successful) mutation. It must keep its result.
    expect(ids()).toEqual([1, 2, 3, 9]);
  });

  it('isLoading stays true until every overlapping mutation settles', async () => {
    const first = deferred();
    const second = deferred();
    const { result } = setup({
      post: vi.fn().mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise),
    });

    act(() => {
      void result.current.addTrack(track(9));
      void result.current.addTrack(track(8));
    });
    expect(result.current.isLoading).toBe(true);

    await act(async () => {
      first.resolve({});
    });
    // The first mutation settled, the second is still in flight: the old
    // boolean dropped to false here.
    expect(result.current.isLoading).toBe(true);

    await act(async () => {
      second.resolve({});
    });
    expect(result.current.isLoading).toBe(false);
  });
});
