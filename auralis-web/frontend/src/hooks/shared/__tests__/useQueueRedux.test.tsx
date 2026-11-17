/**
 * Direct spec for useQueueRedux (#5683): imports the module itself, not the useReduxState barrel.
 */
import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { Provider } from 'react-redux';
import type { ReactNode } from 'react';
import { createTestStore } from '@/test/test-utils';
import type { QueueTrack } from '@/types/domain';
import { setCurrentTime } from '@/store/slices/playerSlice';
import { useQueue, useQueueState } from '../useQueueRedux';

const track = (id: number, duration: number) =>
  ({ id, title: `T${id}`, artist: 'A', album: 'B', duration }) as unknown as QueueTrack;

function setup(queue?: Record<string, unknown>) {
  const store = createTestStore(queue ? { queue: queue as never } : undefined);
  const wrapper = ({ children }: { children: ReactNode }) => <Provider store={store}>{children}</Provider>;
  return { store, wrapper };
}

describe('useQueueState', () => {
  it('reads the queue slice', () => {
    const { wrapper } = setup({ tracks: [track(1, 10)], currentIndex: 0 });
    const { result } = renderHook(() => useQueueState(), { wrapper });
    expect(result.current.tracks.map((t) => t.id)).toEqual([1]);
  });
});

describe('useQueue', () => {
  it('derives current track, length and the remaining/total durations', () => {
    const { wrapper } = setup({ tracks: [track(1, 100), track(2, 50), track(3, 25)], currentIndex: 1 });
    const { result } = renderHook(() => useQueue(), { wrapper });

    expect(result.current.currentTrack?.id).toBe(2);
    expect(result.current.queueLength).toBe(3);
    expect(result.current.totalTime).toBe(175);
    expect(result.current.remainingTime).toBe(25); // only what follows the current track
  });

  it('has no current track for an empty queue', () => {
    const { wrapper } = setup();
    const { result } = renderHook(() => useQueue(), { wrapper });
    expect(result.current.currentTrack).toBeNull();
    expect(result.current.totalTime).toBe(0);
  });

  it('add, addMany, remove, reorder, setCurrentIndex, setQueue and clear dispatch to the slice', () => {
    const { store, wrapper } = setup();
    const { result } = renderHook(() => useQueue(), { wrapper });
    const ids = () => store.getState().queue.tracks.map((t) => t.id);

    act(() => { result.current.add(track(1, 1)); });
    act(() => { result.current.addMany([track(2, 1), track(3, 1)]); });
    expect(ids()).toEqual([1, 2, 3]);

    act(() => { result.current.reorder(0, 2); });
    expect(ids()).toEqual([2, 3, 1]);

    act(() => { result.current.remove(1); });
    expect(ids()).toEqual([2, 1]);

    act(() => { result.current.setCurrentIndex(1); });
    expect(store.getState().queue.currentIndex).toBe(1);

    act(() => { result.current.setQueue([track(9, 1)]); });
    expect(ids()).toEqual([9]);

    act(() => { result.current.clear(); });
    expect(ids()).toEqual([]);
  });

  it('add honours an insert position', () => {
    const { store, wrapper } = setup({ tracks: [track(1, 1), track(2, 1)], currentIndex: 0 });
    const { result } = renderHook(() => useQueue(), { wrapper });

    act(() => { result.current.add(track(7, 1), 1); });
    expect(store.getState().queue.tracks.map((t) => t.id)).toEqual([1, 7, 2]);
  });

  it('keeps one object identity while nothing it exposes changes', () => {
    const { store, wrapper } = setup({ tracks: [track(1, 1)], currentIndex: 0 });
    const { result } = renderHook(() => useQueue(), { wrapper });
    const first = result.current;

    act(() => { store.dispatch(setCurrentTime(3)); });
    expect(result.current).toBe(first);
  });
});
