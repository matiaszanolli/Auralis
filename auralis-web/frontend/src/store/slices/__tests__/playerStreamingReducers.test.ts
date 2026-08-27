/**
 * Streaming reducers survive being defined outside the slice (#5042)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * The five `player.streaming.*` reducers now live in
 * ./playerStreamingReducers and are spread into `createSlice`. That splits the
 * file, not the slice — but only as long as RTK still derives the action type
 * from the slice name plus the reducer key. If a future change nested them
 * instead of spreading, or moved them into their own slice, the action strings
 * would silently become something else and every `dispatch(...)` call site plus
 * the error-tracking allowlist would drift with them.
 *
 * So this pins the strings themselves, not just the behaviour.
 */

import { describe, it, expect } from 'vitest';

import reducer, {
  startStreaming,
  updateStreamingProgress,
  completeStreaming,
  setStreamingError,
  resetStreaming,
  setIsPlaying,
} from '../playerSlice';
import { initialStreamingInfo } from '../playerStreamingReducers';

describe('streaming reducer action types (#5042)', () => {
  it('keeps the `player/` prefix the spread is supposed to preserve', () => {
    expect(startStreaming.type).toBe('player/startStreaming');
    expect(updateStreamingProgress.type).toBe('player/updateStreamingProgress');
    expect(completeStreaming.type).toBe('player/completeStreaming');
    expect(setStreamingError.type).toBe('player/setStreamingError');
    expect(resetStreaming.type).toBe('player/resetStreaming');
  });

  it('matches the prefix of the flat reducers defined inline in the slice', () => {
    // Externally-defined and inline reducers must be indistinguishable on the wire.
    expect(startStreaming.type.split('/')[0]).toBe(setIsPlaying.type.split('/')[0]);
  });
});

describe('streaming sub-state transitions (#5042)', () => {
  const base = () => reducer(undefined, { type: '@@INIT' });

  it('startStreaming arms the requested stream and leaves its sibling alone', () => {
    const next = reducer(
      base(),
      startStreaming({ streamType: 'enhanced', trackId: 7, totalChunks: 12, intensity: 0.5 })
    );

    expect(next.streaming.enhanced).toMatchObject({
      state: 'buffering',
      trackId: 7,
      totalChunks: 12,
      intensity: 0.5,
      processedChunks: 0,
      progress: 0,
      error: null,
    });
    expect(next.streaming.normal).toEqual(initialStreamingInfo);
  });

  it('updateStreamingProgress promotes buffering to streaming once samples land', () => {
    let state = reducer(
      base(),
      startStreaming({ streamType: 'normal', trackId: 1, totalChunks: 4, intensity: 1 })
    );
    state = reducer(
      state,
      updateStreamingProgress({
        streamType: 'normal',
        processedChunks: 1,
        bufferedSamples: 4410,
        progress: 25,
      })
    );

    expect(state.streaming.normal.state).toBe('streaming');
    expect(state.streaming.normal.progress).toBe(25);
  });

  it('drops progress, completion and errors from a superseded track (#4434)', () => {
    const armed = reducer(
      base(),
      startStreaming({ streamType: 'enhanced', trackId: 1, totalChunks: 4, intensity: 1 })
    );

    const stale = reducer(
      armed,
      updateStreamingProgress({
        streamType: 'enhanced',
        processedChunks: 4,
        bufferedSamples: 999,
        progress: 100,
        trackId: 2, // a track the user already skipped away from
      })
    );
    expect(stale.streaming.enhanced.progress).toBe(0);

    expect(
      reducer(armed, completeStreaming({ streamType: 'enhanced', trackId: 2 })).streaming.enhanced.state
    ).toBe('buffering');

    expect(
      reducer(armed, setStreamingError({ streamType: 'enhanced', error: 'boom', trackId: 2 }))
        .streaming.enhanced.state
    ).toBe('buffering');
  });

  it('completeStreaming still accepts a bare streamType', () => {
    // Back-compat branch in the prepare callback.
    const done = reducer(base(), completeStreaming('normal'));
    expect(done.streaming.normal).toMatchObject({ state: 'complete', progress: 100 });
  });

  it('resetStreaming restores the initial sub-state', () => {
    let state = reducer(
      base(),
      startStreaming({ streamType: 'normal', trackId: 3, totalChunks: 9, intensity: 1 })
    );
    state = reducer(state, resetStreaming('normal'));

    expect(state.streaming.normal).toEqual(initialStreamingInfo);
  });

  it('stamps lastUpdated from the prepare callback', () => {
    const next = reducer(base(), resetStreaming('enhanced'));
    expect(next.lastUpdated).toBeGreaterThan(0);
  });
});
