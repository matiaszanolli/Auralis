/**
 * useQueueMutations reorder routing — regression tests (#4854)
 *
 * The backend has two distinct reorder routes with two distinct body models:
 *
 *   PUT /api/player/queue/move     MoveQueueTrackRequest { from_index, to_index }
 *   PUT /api/player/queue/reorder  ReorderQueueRequest   { new_order: int[] }
 *
 * `reorderTrack` sent `{from_index, to_index}` to `/reorder`, so FastAPI
 * rejected it with 422 (`body.new_order Field required`) before any handler ran.
 * `runOptimistic` then rolled Redux back, so the row visibly snapped to its
 * original position with only a console.error — no user-facing failure.
 *
 * Both the mouse drag path and the keyboard path added by #4536 route through
 * `reorderTrack`, so neither has ever worked end-to-end; #4536 was verified and
 * closed against a reorder that could not reach its handler.
 *
 * These pin the (route, body) pairing for BOTH mutations, because the failure
 * mode is sending a well-formed body to the wrong one of two sibling routes —
 * asserting only that `put` was called cannot catch it.
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

let store: ReturnType<typeof configureStore>;
let put: ReturnType<typeof vi.fn>;

const setup = (putImpl?: () => Promise<unknown>) => {
  store = configureStore({ reducer: { queue: queueReducer } });
  store.dispatch(reduxSetQueue(seed));
  put = vi.fn().mockImplementation(putImpl ?? (() => Promise.resolve({})));

  vi.spyOn(useRestAPIModule, 'useRestAPI').mockReturnValue({
    get: vi.fn(),
    post: vi.fn().mockResolvedValue({}),
    put,
    patch: vi.fn(),
    delete: vi.fn().mockResolvedValue({}),
  } as unknown as ReturnType<typeof useRestAPIModule.useRestAPI>);

  const wrapper = ({ children }: { children: ReactNode }) =>
    createElement(Provider, { store, children });

  return renderHook(() => useQueueMutations(), { wrapper });
};

const ids = () => ((store.getState() as any).queue.tracks as Track[]).map((t) => t.id);

describe('reorderTrack route (#4854)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('sends a single-item move to /queue/move', async () => {
    const { result } = setup();

    await act(async () => {
      await result.current.reorderTrack(0, 2);
    });

    expect(put).toHaveBeenCalledWith('/api/player/queue/move', {
      from_index: 0,
      to_index: 2,
    });
  });

  it('never sends {from_index,to_index} to /queue/reorder', async () => {
    const { result } = setup();

    await act(async () => {
      await result.current.reorderTrack(1, 0);
    });

    const [route, body] = put.mock.calls[0];
    expect(route).not.toBe('/api/player/queue/reorder');
    // The shape the /reorder model would have required, and did not get.
    expect(body).not.toHaveProperty('new_order');
  });

  it('keeps the optimistic reorder when the request succeeds', async () => {
    const { result } = setup();

    await act(async () => {
      await result.current.reorderTrack(0, 2);
    });

    expect(ids()).toEqual([2, 3, 1]);
  });

  it('rolls the row back when the request fails (the observed 422 symptom)', async () => {
    const { result } = setup(() => Promise.reject(new Error('HTTP 422: Unprocessable Entity')));

    await act(async () => {
      await expect(result.current.reorderTrack(0, 2)).rejects.toBeDefined();
    });

    expect(ids()).toEqual([1, 2, 3]);
  });
});

describe('reorderQueue route (the sibling that was already correct)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('sends a full permutation to /queue/reorder', async () => {
    const { result } = setup();

    await act(async () => {
      await result.current.reorderQueue([2, 0, 1]);
    });

    expect(put).toHaveBeenCalledWith('/api/player/queue/reorder', {
      new_order: [2, 0, 1],
    });
  });

  it('never sends new_order to /queue/move', async () => {
    const { result } = setup();

    await act(async () => {
      await result.current.reorderQueue([2, 0, 1]);
    });

    const [route] = put.mock.calls[0];
    expect(route).not.toBe('/api/player/queue/move');
  });

  it('the two mutations use different routes', async () => {
    const { result } = setup();

    await act(async () => {
      await result.current.reorderTrack(0, 1);
      await result.current.reorderQueue([2, 0, 1]);
    });

    const routes = put.mock.calls.map((c: unknown[]) => c[0]);
    expect(routes).toEqual(['/api/player/queue/move', '/api/player/queue/reorder']);
  });
});
