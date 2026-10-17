/**
 * setCurrentTrackAndSyncQueue resolves the queue slot, not just the track id (#5600)
 *
 * The queue may hold the same track twice (context-menu "Add to Queue" does
 * not dedupe). The thunk used to `findIndex` by id, which always answers with
 * the first copy, so Next from `[A, B, A, C]` at B wrote index 0 and the
 * Next/auto-advance chain looped A -> B -> A without ever reaching C.
 */

import { describe, it, expect } from 'vitest';
import { configureStore } from '@reduxjs/toolkit';
import playerReducer, { setCurrentTrack } from '../playerSlice';
import { setCurrentTrackAndSyncQueue } from '../playerQueueSync';
import cacheReducer from '../cacheSlice';
import connectionReducer from '../connectionSlice';
import queueReducer, { setQueue, setCurrentIndex } from '../queueSlice';
import type { QueueTrack } from '@/types/domain';

const track = (id: number): QueueTrack => ({
  id,
  title: `Track ${id}`,
  artist: 'Artist',
  album: 'Album',
  duration: 100,
  artworkUrl: null,
});

const [A, B, C] = [track(1), track(2), track(3)];

function makeStore(queue: QueueTrack[], currentIndex: number) {
  const store = configureStore({
    reducer: {
      player: playerReducer,
      queue: queueReducer,
      cache: cacheReducer,
      connection: connectionReducer,
    },
  });
  store.dispatch(setQueue(queue));
  store.dispatch(setCurrentIndex(currentIndex));
  return store;
}

const index = (store: ReturnType<typeof makeStore>) => store.getState().queue.currentIndex;

describe('setCurrentTrackAndSyncQueue (#5600)', () => {
  it('uses the explicit index when the queue holds the track twice', () => {
    const store = makeStore([A, B, A, C], 1);

    store.dispatch(setCurrentTrackAndSyncQueue(A, 2));

    expect(index(store)).toBe(2);
    expect(store.getState().player.currentTrack?.id).toBe(A.id);
  });

  it('walks [A, B, A, C] forward through every slot, reaching C', () => {
    const store = makeStore([A, B, A, C], 0);
    const queue = store.getState().queue.tracks;
    const visited: number[] = [];

    for (let next = 1; next < queue.length; next++) {
      store.dispatch(setCurrentTrackAndSyncQueue(queue[next] as never, next));
      visited.push(index(store));
    }

    expect(visited).toEqual([1, 2, 3]);
  });

  it('walks backwards from the second copy to B, not to slot 0', () => {
    const store = makeStore([A, B, A, C], 2);

    store.dispatch(setCurrentTrackAndSyncQueue(B, 1));

    expect(index(store)).toBe(1);
  });

  it('without an index picks the copy nearest the current slot', () => {
    // The post-fetch dispatch in useEnhancedPlayCommand only knows the id; the
    // thunk already moved the index to the right copy, so it must stay there.
    const second = makeStore([A, B, A, C], 2);
    second.dispatch(setCurrentTrackAndSyncQueue(A));
    expect(index(second)).toBe(2);

    const first = makeStore([A, B, A, C], 0);
    first.dispatch(setCurrentTrackAndSyncQueue(A));
    expect(index(first)).toBe(0);
  });

  it('prefers the later copy when two are equally near', () => {
    const store = makeStore([A, B, A, C], 1);

    store.dispatch(setCurrentTrackAndSyncQueue(A));

    expect(index(store)).toBe(2);
  });

  it('ignores an index that does not hold the track and falls back to the nearest copy', () => {
    const store = makeStore([A, B, A, C], 2);

    store.dispatch(setCurrentTrackAndSyncQueue(A, 3)); // slot 3 is C

    expect(index(store)).toBe(2);
  });

  it('leaves the queue index alone when the track is not queued', () => {
    const store = makeStore([A, B], 1);

    store.dispatch(setCurrentTrackAndSyncQueue(C));

    expect(index(store)).toBe(1);
    expect(store.getState().player.currentTrack?.id).toBe(C.id);
  });

  it('clears the current track without touching the queue index', () => {
    const store = makeStore([A, B], 1);
    store.dispatch(setCurrentTrack(B as never));

    store.dispatch(setCurrentTrackAndSyncQueue(null));

    expect(store.getState().player.currentTrack).toBeNull();
    expect(index(store)).toBe(1);
  });
});
