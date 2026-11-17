/**
 * Redux Selector Tests
 * ~~~~~~~~~~~~~~~~~~~~~
 *
 * Verifies memoization correctness for the selectors that have a production consumer: the same
 * reference on repeated calls with unchanged state, a new one when relevant state changes, and
 * correct derived values. The cache/connection selectors, the combined snapshot objects and the
 * 1 Hz playback selectors had no consumer and were deleted with their tests (#5129, #6040).
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { setIsPlaying } from '@/store/slices/playerSlice';
import { setQueue, setCurrentIndex } from '@/store/slices/queueSlice';
import {
  playerSelectors,
  selectCurrentQueueTrack,
  selectRemainingTime,
  selectTotalQueueTime,
  selectFormattedRemainingTime,
} from '../index';
import type { RootState } from '@/store/index';
import { createTestStore } from '@/test/test-utils';

// ============================================================================
// Test store helpers
// ============================================================================

type TestStore = ReturnType<typeof createTestStore>;

const mockTrack = (id: number, duration = 180) => ({
  id,
  title: `Track ${id}`,
  artist: 'Artist',
  album: 'Album',
  duration,
});

// ============================================================================
// Simple (pass-through) selectors
// ============================================================================

describe('playerSelectors (simple)', () => {
  let store: TestStore;

  beforeEach(() => {
    store = createTestStore();
  });

  it('selectIsPlaying returns false by default', () => {
    expect(playerSelectors.selectIsPlaying(store.getState() as RootState)).toBe(false);
  });

  it('selectCurrentTrack returns null by default', () => {
    expect(playerSelectors.selectCurrentTrack(store.getState() as RootState)).toBeNull();
  });

  it('selectVolume returns the initial volume (80, per #2251)', () => {
    expect(playerSelectors.selectVolume(store.getState() as RootState)).toBe(80);
  });

  it('reflects dispatched state changes', () => {
    store.dispatch(setIsPlaying(true));
    expect(playerSelectors.selectIsPlaying(store.getState() as RootState)).toBe(true);
  });
});

// ============================================================================
// Memoization: same reference on unchanged state
// ============================================================================

describe('Memoization – same reference on unchanged state', () => {
  let store: TestStore;

  beforeEach(() => {
    store = createTestStore();
    store.dispatch(setQueue([mockTrack(1), mockTrack(2), mockTrack(3)]));
  });

  it('selectCurrentQueueTrack returns same reference across 10 calls', () => {
    const state = store.getState();
    const first = selectCurrentQueueTrack(state as RootState);
    for (let i = 0; i < 9; i++) {
      expect(selectCurrentQueueTrack(state as RootState)).toBe(first);
    }
  });

  it('selectRemainingTime returns same reference across 10 calls', () => {
    const state = store.getState();
    const first = selectRemainingTime(state as RootState);
    for (let i = 0; i < 9; i++) {
      expect(selectRemainingTime(state as RootState)).toBe(first);
    }
  });

});

// ============================================================================
// Memoization: new reference when relevant state changes
// ============================================================================

describe('Memoization – new reference when state changes', () => {
  let store: TestStore;

  beforeEach(() => {
    store = createTestStore();
    store.dispatch(setQueue([mockTrack(1), mockTrack(2)]));
  });

  it('selectCurrentQueueTrack: new object when currentIndex changes', () => {
    const before = selectCurrentQueueTrack(store.getState() as RootState);
    store.dispatch(setCurrentIndex(1));
    const after = selectCurrentQueueTrack(store.getState() as RootState);
    expect(after).not.toBe(before);
    expect(after?.id).toBe(2);
  });

});

// ============================================================================
// Derived value correctness
// ============================================================================

describe('selectCurrentQueueTrack – correctness', () => {
  let store: TestStore;

  beforeEach(() => {
    store = createTestStore();
  });

  it('returns null when queue is empty', () => {
    expect(selectCurrentQueueTrack(store.getState() as RootState)).toBeNull();
  });

  it('returns the track at currentIndex', () => {
    store.dispatch(setQueue([mockTrack(10), mockTrack(20)]));
    store.dispatch(setCurrentIndex(1));
    expect(selectCurrentQueueTrack(store.getState() as RootState)?.id).toBe(20);
  });
});

describe('selectRemainingTime – correctness', () => {
  let store: TestStore;

  beforeEach(() => {
    store = createTestStore();
  });

  it('returns 0 when queue is empty', () => {
    expect(selectRemainingTime(store.getState() as RootState)).toBe(0);
  });

  it('sums durations of tracks after currentIndex', () => {
    store.dispatch(setQueue([mockTrack(1, 60), mockTrack(2, 90), mockTrack(3, 120)]));
    store.dispatch(setCurrentIndex(0));
    expect(selectRemainingTime(store.getState() as RootState)).toBe(210); // 90+120
  });

  it('returns 0 when at last track', () => {
    store.dispatch(setQueue([mockTrack(1, 60), mockTrack(2, 90)]));
    store.dispatch(setCurrentIndex(1));
    expect(selectRemainingTime(store.getState() as RootState)).toBe(0);
  });
});

describe('selectTotalQueueTime – correctness', () => {
  let store: TestStore;

  beforeEach(() => {
    store = createTestStore();
    store.dispatch(setQueue([mockTrack(1, 60), mockTrack(2, 60), mockTrack(3, 60)]));
  });

  it('selectTotalQueueTime returns sum of all durations', () => {
    expect(selectTotalQueueTime(store.getState() as RootState)).toBe(180);
  });
});


describe('selectFormattedRemainingTime', () => {
  let store: TestStore;

  beforeEach(() => {
    store = createTestStore();
    store.dispatch(setQueue([mockTrack(1, 60), mockTrack(2, 90), mockTrack(3, 125)]));
    store.dispatch(setCurrentIndex(0));
  });

  it('formats what follows the current track and returns the same reference while state is unchanged', () => {
    const state = store.getState() as RootState;
    const first = selectFormattedRemainingTime(state);

    expect(first).toEqual({ total: 215, formatted: '3m 35s' });
    expect(selectFormattedRemainingTime(state)).toBe(first);
  });

  it('recomputes when the current index moves', () => {
    const before = selectFormattedRemainingTime(store.getState() as RootState);
    store.dispatch(setCurrentIndex(1));

    expect(selectFormattedRemainingTime(store.getState() as RootState)).toEqual({ total: 125, formatted: '2m 5s' });
    expect(selectFormattedRemainingTime(store.getState() as RootState)).not.toBe(before);
  });
});
