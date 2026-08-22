/**
 * useQueueMutations — stale-rollback regression tests (#4836)
 *
 * Each optimistic mutation snapshots state *before* it applies. When two
 * mutations overlap and the *earlier* one rejects after the later one has
 * already applied, restoring that earlier snapshot undoes the later mutation
 * too — for the queue array that is a wholesale overwrite, discarding a change
 * the server has already accepted.
 *
 * A per-field generation counter now suppresses a rollback that is no longer
 * the newest mutation for that field. The error still reaches the caller; only
 * the state restore is skipped.
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

/** A promise the test settles by hand, so request ordering is deterministic. */
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

const queueState = () =>
  (store.getState() as {
    queue: { tracks: Track[]; isShuffled: boolean; repeatMode: string };
  }).queue;

const ids = () => queueState().tracks.map((t) => t.id);

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('useQueueMutations stale rollbacks (#4836)', () => {
  it('keeps a later succeeded mutation when an earlier one fails afterwards', async () => {
    const addRequest = deferred();
    const { result } = setup({
      post: () => addRequest.promise,          // addTrack — slow, will reject
      delete: () => Promise.resolve({}),       // removeTrack — fast, succeeds
    });

    let addCall!: Promise<void>;
    act(() => {
      addCall = result.current.addTrack(track(9));
    });
    expect(ids()).toEqual([1, 2, 3, 9]);

    // B applies on top of A's optimistic state and its request succeeds.
    await act(async () => {
      await result.current.removeTrack(0);
    });
    expect(ids()).toEqual([2, 3, 9]);

    // A only now rejects. Its snapshot is [1, 2, 3] — pre-A and pre-B.
    await act(async () => {
      addRequest.reject(new Error('boom'));
      await expect(addCall).rejects.toBeDefined();
    });

    expect(ids()).toEqual([2, 3, 9]);
    expect(result.current.error?.code).toBe('ADD_TRACK_ERROR');
  });

  it('still rolls back when the failing mutation is the newest one', async () => {
    const { result } = setup({ post: () => Promise.reject(new Error('boom')) });

    await act(async () => {
      await expect(result.current.addTrack(track(9))).rejects.toBeDefined();
    });

    expect(ids()).toEqual([1, 2, 3]);
  });

  it('does not let a stale shuffle rollback undo a newer toggle', async () => {
    const first = deferred();
    let call = 0;
    const { result } = setup({
      post: () => (call++ === 0 ? first.promise : Promise.resolve({})),
    });

    let firstToggle!: Promise<void>;
    act(() => {
      firstToggle = result.current.toggleShuffle();
    });
    expect(queueState().isShuffled).toBe(true);

    // Two more toggles land back on `true`; a single-step stale rollback would
    // restore `false`, so the assertion below can tell them apart.
    // Separate act() calls so the hook re-renders between them and `stateRef`
    // sees each new value before the next toggle reads it.
    await act(async () => {
      await result.current.toggleShuffle();
    });
    await act(async () => {
      await result.current.toggleShuffle();
    });
    expect(queueState().isShuffled).toBe(true);

    await act(async () => {
      first.reject(new Error('boom'));
      await expect(firstToggle).rejects.toBeDefined();
    });

    expect(queueState().isShuffled).toBe(true);
    expect(result.current.error?.code).toBe('SHUFFLE_ERROR');
  });

  it('does not let a stale repeat-mode rollback undo a newer mode change', async () => {
    const first = deferred();
    let call = 0;
    const { result } = setup({
      post: () => (call++ === 0 ? first.promise : Promise.resolve({})),
    });

    let firstChange!: Promise<void>;
    act(() => {
      firstChange = result.current.setRepeatMode('all');
    });
    expect(queueState().repeatMode).toBe('all');

    await act(async () => {
      await result.current.setRepeatMode('one');
    });
    expect(queueState().repeatMode).toBe('one');

    await act(async () => {
      first.reject(new Error('boom'));
      await expect(firstChange).rejects.toBeDefined();
    });

    // Without the generation guard this reverts to 'off' — the mode in effect
    // before the *first* change — discarding the mode the server accepted.
    expect(queueState().repeatMode).toBe('one');
    expect(result.current.error?.code).toBe('REPEAT_MODE_ERROR');
  });

  it('still rolls back a repeat-mode change that is the newest one', async () => {
    const { result } = setup({ post: () => Promise.reject(new Error('boom')) });

    await act(async () => {
      await expect(result.current.setRepeatMode('all')).rejects.toBeDefined();
    });

    expect(queueState().repeatMode).toBe('off');
  });
});
