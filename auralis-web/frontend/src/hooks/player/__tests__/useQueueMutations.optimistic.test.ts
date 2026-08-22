/**
 * useQueueMutations — optimistic update regression tests (#4583)
 *
 * The hook's docblock promised "optimistic Redux updates and rollback-on-error"
 * but only setQueue/toggleShuffle/setRepeatMode/clearQueue delivered it.
 * addTrack/removeTrack/reorderTrack/reorderQueue dispatched nothing and waited
 * for the REST round-trip plus the `queue_changed` broadcast, so a drag-and-drop
 * reorder visibly snapped back until the PUT resolved.
 *
 * Each mutation is asserted twice: the store reflects the change while the
 * request is still in flight, and a rejected request restores the prior order
 * *and* re-throws so callers (QueuePanel) still see the failure.
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

/** A promise that never settles — models "request still in flight". */
const pending = () => new Promise<never>(() => {});

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

describe('useQueueMutations optimistic updates (#4583)', () => {
  describe('reorderTrack', () => {
    it('applies the new order before the PUT resolves', async () => {
      const { result } = setup({ put: pending });

      act(() => {
        void result.current.reorderTrack(0, 2);
      });

      expect(ids()).toEqual([2, 3, 1]);
    });

    it('restores the previous order when the PUT rejects, and re-throws', async () => {
      const { result } = setup({ put: () => Promise.reject(new Error('boom')) });

      await act(async () => {
        await expect(result.current.reorderTrack(0, 2)).rejects.toBeDefined();
      });

      expect(ids()).toEqual([1, 2, 3]);
    });
  });

  describe('removeTrack', () => {
    it('removes the row immediately', async () => {
      const { result } = setup({ delete: pending });

      act(() => {
        void result.current.removeTrack(1);
      });

      expect(ids()).toEqual([1, 3]);
    });

    it('restores the removed row on failure', async () => {
      const { result } = setup({ delete: () => Promise.reject(new Error('boom')) });

      await act(async () => {
        await expect(result.current.removeTrack(1)).rejects.toBeDefined();
      });

      expect(ids()).toEqual([1, 2, 3]);
    });
  });

  describe('addTrack', () => {
    it('appends immediately when no position is given', async () => {
      const { result } = setup({ post: pending });

      act(() => {
        void result.current.addTrack(track(9));
      });

      expect(ids()).toEqual([1, 2, 3, 9]);
    });

    it('inserts at the requested position immediately', async () => {
      const { result } = setup({ post: pending });

      act(() => {
        void result.current.addTrack(track(9), 1);
      });

      expect(ids()).toEqual([1, 9, 2, 3]);
    });

    it('removes the optimistically added track on failure', async () => {
      const { result } = setup({ post: () => Promise.reject(new Error('boom')) });

      await act(async () => {
        await expect(result.current.addTrack(track(9))).rejects.toBeDefined();
      });

      expect(ids()).toEqual([1, 2, 3]);
    });
  });

  describe('reorderQueue', () => {
    it('applies the index permutation immediately', async () => {
      const { result } = setup({ put: pending });

      act(() => {
        // `new_order` is a permutation of INDICES: new[0] = old[2], etc.
        void result.current.reorderQueue([2, 0, 1]);
      });

      expect(ids()).toEqual([3, 1, 2]);
    });

    it('keeps the current pointer on the same track, as the backend does', async () => {
      const { result } = setup({ put: pending });

      act(() => {
        void result.current.reorderQueue([2, 0, 1]);
      });

      // Track 1 was current (index 0) and is now at index 1.
      const state = store.getState() as { queue: { currentIndex: number } };
      expect(state.queue.currentIndex).toBe(1);
    });

    it('restores the original order on failure', async () => {
      const { result } = setup({ put: () => Promise.reject(new Error('boom')) });

      await act(async () => {
        await expect(result.current.reorderQueue([2, 0, 1])).rejects.toBeDefined();
      });

      expect(ids()).toEqual([1, 2, 3]);
    });

    it('does not apply a permutation the backend would reject', async () => {
      const { result } = setup({ put: pending });

      act(() => {
        void result.current.reorderQueue([0, 1]); // wrong length
      });

      expect(ids()).toEqual([1, 2, 3]);
    });
  });

  describe('setRepeatMode', () => {
    it('does not wedge isLoading when the mode is invalid', async () => {
      const { result } = setup({});

      await act(async () => {
        await expect(
          result.current.setRepeatMode('sideways' as 'off')
        ).rejects.toBeDefined();
      });

      // The old order set isLoading true and threw before the finally block
      // existed, leaving every queue control disabled forever.
      expect(result.current.isLoading).toBe(false);
    });
  });
});
