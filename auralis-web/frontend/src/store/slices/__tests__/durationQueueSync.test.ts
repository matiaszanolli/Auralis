/**
 * player/queue duration divergence (#4580)
 *
 * The app keeps two independent records of the current track —
 * `player.currentTrack` and `queue.tracks[currentIndex]` — with structurally
 * identical types. `setDuration` patches the player copy (#2774) but cannot
 * reach the queue slice, so a `player_state` snapshot carrying a re-analysed
 * duration without a fresh queue array left the queue's "time remaining",
 * total time and per-row durations showing the pre-correction value
 * indefinitely, while the progress bar showed the corrected one.
 */

import { describe, it, expect } from 'vitest';
import { configureStore } from '@reduxjs/toolkit';
import playerReducer, {
  setCurrentTrack,
  setCurrentTime,
  setDuration,
} from '../playerSlice';
import { setDurationAndSyncQueue } from '../playerQueueSync';
import cacheReducer from '../cacheSlice';
import connectionReducer from '../connectionSlice';
import queueReducer, { setQueue, setCurrentIndex, updateTrackById } from '../queueSlice';
import {
  selectCurrentQueueTrack,
  selectRemainingTime,
  selectTotalQueueTime,
} from '@/store/selectors/queue';
import type { QueueTrack } from '@/types/domain';

const track = (id: number, duration: number): QueueTrack => ({
  id,
  title: `Track ${id}`,
  artist: 'Artist',
  album: 'Album',
  duration,
  artworkUrl: null,
});

const makeStore = () => {
  const store = configureStore({
    reducer: {
      player: playerReducer,
      queue: queueReducer,
      // The queue selectors are typed against the full RootState.
      cache: cacheReducer,
      connection: connectionReducer,
    },
  });
  store.dispatch(setQueue([track(1, 200), track(2, 300), track(3, 100)]));
  store.dispatch(setCurrentIndex(0));
  store.dispatch(setCurrentTrack(track(1, 200)));
  return store;
};

describe('updateTrackById (#4580)', () => {
  it('patches the queue record for the given track id', () => {
    const store = makeStore();
    store.dispatch(updateTrackById({ id: 1, changes: { duration: 180 } }));

    expect(store.getState().queue.tracks[0].duration).toBe(180);
  });

  it('patches every occurrence of the track, not just currentIndex', () => {
    // The same track can legitimately sit in a queue more than once; a
    // corrected duration is a property of the track, not of the slot.
    const store = makeStore();
    store.dispatch(setQueue([track(1, 200), track(2, 300), track(1, 200)]));

    store.dispatch(updateTrackById({ id: 1, changes: { duration: 180 } }));

    const durations = store.getState().queue.tracks.map((t) => t.duration);
    expect(durations).toEqual([180, 300, 180]);
  });

  it('leaves other tracks untouched', () => {
    const store = makeStore();
    store.dispatch(updateTrackById({ id: 1, changes: { duration: 180 } }));

    expect(store.getState().queue.tracks[1].duration).toBe(300);
    expect(store.getState().queue.tracks[2].duration).toBe(100);
  });

  it('is a no-op for an id that is not in the queue', () => {
    const store = makeStore();
    const before = store.getState().queue;

    store.dispatch(updateTrackById({ id: 999, changes: { duration: 1 } }));

    const after = store.getState().queue;
    expect(after.tracks).toEqual(before.tracks);
    expect(after.lastUpdated).toBe(before.lastUpdated);
  });

  it('accepts a generic field patch, not just duration', () => {
    // artworkUrl has the same structural exposure; nothing writes it
    // one-sidedly today, but covering it must not need new plumbing.
    const store = makeStore();
    store.dispatch(updateTrackById({ id: 1, changes: { artworkUrl: '/api/albums/5/artwork' } }));

    expect(store.getState().queue.tracks[0].artworkUrl).toBe('/api/albums/5/artwork');
    expect(store.getState().queue.tracks[0].duration).toBe(200);
  });
});

describe('setDurationAndSyncQueue (#4580)', () => {
  it('moves both records together', () => {
    const store = makeStore();
    store.dispatch(setDurationAndSyncQueue(180));

    const state = store.getState();
    expect(state.player.duration).toBe(180);
    expect(state.player.currentTrack?.duration).toBe(180);
    expect(state.queue.tracks[0].duration).toBe(180);
  });

  it('makes the queue selectors reflect the correction', () => {
    const store = makeStore();
    store.dispatch(setCurrentIndex(0));

    // Before: total 200+300+100, remaining (after index 0) 300+100.
    expect(selectTotalQueueTime(store.getState())).toBe(600);

    store.dispatch(setDurationAndSyncQueue(180));

    expect(selectTotalQueueTime(store.getState())).toBe(580);
    expect(selectCurrentQueueTrack(store.getState())?.duration).toBe(180);
  });

  it('reflects the correction in remaining time when the current track is not first', () => {
    const store = makeStore();
    store.dispatch(setCurrentIndex(1));
    store.dispatch(setCurrentTrack(track(2, 300)));

    expect(selectRemainingTime(store.getState())).toBe(100); // track 3 only

    // Correct track 3's duration via a queue patch and confirm the selector moves.
    store.dispatch(updateTrackById({ id: 3, changes: { duration: 50 } }));
    expect(selectRemainingTime(store.getState())).toBe(50);
  });

  it('still updates the player when there is no current track', () => {
    const store = makeStore();
    store.dispatch(setCurrentTrack(null));

    store.dispatch(setDurationAndSyncQueue(180));

    expect(store.getState().player.duration).toBe(180);
    // Queue untouched — no track id to key on.
    expect(store.getState().queue.tracks[0].duration).toBe(200);
  });

  it('preserves the currentTime re-clamp from #4191', () => {
    const store = makeStore();
    store.dispatch(setDurationAndSyncQueue(200));
    // Push currentTime near the end, then shorten the track.
    store.dispatch(setCurrentTime(195));

    store.dispatch(setDurationAndSyncQueue(180));

    expect(store.getState().player.currentTime).toBe(180);
  });
});

describe('the divergence this fixes', () => {
  it('plain setDuration still leaves the queue copy stale', () => {
    // Documents *why* the thunk exists: the reducer alone cannot reach the
    // other slice. If this ever starts passing, the two records were
    // normalised and the thunk is redundant.
    const store = makeStore();
    store.dispatch(setDuration(180));

    expect(store.getState().player.currentTrack?.duration).toBe(180);
    expect(store.getState().queue.tracks[0].duration).toBe(200);
  });
});
