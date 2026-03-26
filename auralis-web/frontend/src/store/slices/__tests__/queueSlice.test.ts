/**
 * queueSlice reducer unit tests (#2815)
 *
 * Covers all action creators, index adjustment logic, and selectors.
 */

import reducer, {
  addTrack,
  addTracks,
  removeTrack,
  reorderTrack,
  clearQueue,
  setQueue,
  setCurrentIndex,
  nextTrack,
  previousTrack,
  setIsLoading,
  setError,
  clearError,
  resetQueue,
  selectQueueTracks,
  selectCurrentIndex,
  selectQueueLength,
  selectIsLoading,
  selectError,
} from '../queueSlice';
import { selectCurrentQueueTrack } from '@/store/selectors';
import type { QueueState } from '../queueSlice';
import type { QueueTrack } from '@/types/domain';

const initialState: QueueState = {
  tracks: [],
  currentIndex: 0,
  isLoading: false,
  error: null,
  lastUpdated: 0,
  isShuffled: false,
  repeatMode: 'off',
};

const mockTrack = (id: number): QueueTrack => ({
  id,
  title: `Track ${id}`,
  artist: `Artist ${id}`,
  album: `Album ${id}`,
  duration: 200 + id,
  artworkUrl: null,
});

describe('queueSlice', () => {
  it('should return initial state', () => {
    const state = reducer(undefined, { type: 'unknown' });
    expect(state.tracks).toEqual([]);
    expect(state.currentIndex).toBe(0);
    expect(state.isLoading).toBe(false);
    expect(state.error).toBeNull();
  });

  // ─── Add/Remove ───────────────────────────────────────────────

  it('addTrack appends track and sets timestamp', () => {
    const state = reducer(initialState, addTrack(mockTrack(1)));
    expect(state.tracks).toHaveLength(1);
    expect(state.tracks[0].id).toBe(1);
    expect(state.lastUpdated).toBeGreaterThan(0);
  });

  it('addTracks appends multiple tracks', () => {
    const state = reducer(initialState, addTracks([mockTrack(1), mockTrack(2)]));
    expect(state.tracks).toHaveLength(2);
  });

  it('removeTrack removes by index', () => {
    let state = reducer(initialState, addTracks([mockTrack(1), mockTrack(2), mockTrack(3)]));
    state = reducer(state, removeTrack(1));
    expect(state.tracks).toHaveLength(2);
    expect(state.tracks[0].id).toBe(1);
    expect(state.tracks[1].id).toBe(3);
  });

  it('removeTrack adjusts currentIndex when removing before it', () => {
    let state = reducer(initialState, addTracks([mockTrack(1), mockTrack(2), mockTrack(3)]));
    state = { ...state, currentIndex: 2 };
    state = reducer(state, removeTrack(0));
    expect(state.currentIndex).toBe(1);
  });

  it('removeTrack adjusts currentIndex when removing at end', () => {
    let state = reducer(initialState, addTracks([mockTrack(1), mockTrack(2)]));
    state = { ...state, currentIndex: 1 };
    state = reducer(state, removeTrack(1));
    expect(state.currentIndex).toBe(0);
  });

  it('removeTrack ignores out-of-range index', () => {
    let state = reducer(initialState, addTrack(mockTrack(1)));
    state = reducer(state, removeTrack(5));
    expect(state.tracks).toHaveLength(1);
  });

  // ─── Reorder ──────────────────────────────────────────────────

  it('reorderTrack moves track forward', () => {
    let state = reducer(initialState, addTracks([mockTrack(1), mockTrack(2), mockTrack(3)]));
    state = reducer(state, reorderTrack({ fromIndex: 0, toIndex: 2 }));
    expect(state.tracks.map((t) => t.id)).toEqual([2, 3, 1]);
  });

  it('reorderTrack moves track backward', () => {
    let state = reducer(initialState, addTracks([mockTrack(1), mockTrack(2), mockTrack(3)]));
    state = reducer(state, reorderTrack({ fromIndex: 2, toIndex: 0 }));
    expect(state.tracks.map((t) => t.id)).toEqual([3, 1, 2]);
  });

  it('reorderTrack updates currentIndex when current track is moved', () => {
    let state = reducer(initialState, addTracks([mockTrack(1), mockTrack(2), mockTrack(3)]));
    state = { ...state, currentIndex: 0 };
    state = reducer(state, reorderTrack({ fromIndex: 0, toIndex: 2 }));
    expect(state.currentIndex).toBe(2);
  });

  it('reorderTrack is no-op when fromIndex equals toIndex', () => {
    let state = reducer(initialState, addTracks([mockTrack(1), mockTrack(2)]));
    const before = state.lastUpdated;
    state = reducer(state, reorderTrack({ fromIndex: 0, toIndex: 0 }));
    expect(state.lastUpdated).toBe(before);
  });

  // ─── Queue operations ────────────────────────────────────────

  it('clearQueue empties tracks and resets index', () => {
    let state = reducer(initialState, addTracks([mockTrack(1), mockTrack(2)]));
    state = { ...state, currentIndex: 1 };
    state = reducer(state, clearQueue());
    expect(state.tracks).toEqual([]);
    expect(state.currentIndex).toBe(0);
  });

  it('setQueue replaces entire queue and clamps index', () => {
    let state = reducer(initialState, addTracks([mockTrack(1), mockTrack(2), mockTrack(3)]));
    state = { ...state, currentIndex: 2 };
    state = reducer(state, setQueue([mockTrack(4)]));
    expect(state.tracks).toHaveLength(1);
    expect(state.currentIndex).toBe(0); // clamped
  });

  // ─── Navigation ───────────────────────────────────────────────

  it('setCurrentIndex sets valid index', () => {
    let state = reducer(initialState, addTracks([mockTrack(1), mockTrack(2)]));
    state = reducer(state, setCurrentIndex(1));
    expect(state.currentIndex).toBe(1);
  });

  it('setCurrentIndex ignores out-of-range index', () => {
    let state = reducer(initialState, addTrack(mockTrack(1)));
    state = reducer(state, setCurrentIndex(5));
    expect(state.currentIndex).toBe(0);
  });

  it('nextTrack increments index', () => {
    let state = reducer(initialState, addTracks([mockTrack(1), mockTrack(2)]));
    state = reducer(state, nextTrack());
    expect(state.currentIndex).toBe(1);
  });

  it('nextTrack does not go past last track', () => {
    let state = reducer(initialState, addTracks([mockTrack(1), mockTrack(2)]));
    state = { ...state, currentIndex: 1 };
    state = reducer(state, nextTrack());
    expect(state.currentIndex).toBe(1);
  });

  it('previousTrack decrements index', () => {
    let state = reducer(initialState, addTracks([mockTrack(1), mockTrack(2)]));
    state = { ...state, currentIndex: 1 };
    state = reducer(state, previousTrack());
    expect(state.currentIndex).toBe(0);
  });

  it('previousTrack does not go below zero', () => {
    let state = reducer(initialState, addTrack(mockTrack(1)));
    state = reducer(state, previousTrack());
    expect(state.currentIndex).toBe(0);
  });

  // ─── Loading/Error ────────────────────────────────────────────

  it('setIsLoading sets loading state', () => {
    const state = reducer(initialState, setIsLoading(true));
    expect(state.isLoading).toBe(true);
  });

  it('setError sets error message', () => {
    const state = reducer(initialState, setError('fail'));
    expect(state.error).toBe('fail');
  });

  it('clearError clears error', () => {
    let state = reducer(initialState, setError('fail'));
    state = reducer(state, clearError());
    expect(state.error).toBeNull();
  });

  // ─── Reset ────────────────────────────────────────────────────

  it('resetQueue returns to initial state', () => {
    let state = reducer(initialState, addTracks([mockTrack(1), mockTrack(2)]));
    state = reducer(state, setError('fail'));
    state = reducer(state, resetQueue());
    expect(state.tracks).toEqual([]);
    expect(state.currentIndex).toBe(0);
    expect(state.error).toBeNull();
  });

  // ─── Selectors ────────────────────────────────────────────────

  it('selectors return correct values', () => {
    let state = reducer(initialState, addTracks([mockTrack(1), mockTrack(2)]));
    state = { ...state, currentIndex: 1 };
    const root = { queue: state };

    expect(selectQueueTracks(root)).toHaveLength(2);
    expect(selectCurrentIndex(root)).toBe(1);
    expect(selectCurrentQueueTrack(root as any)?.id).toBe(2);
    expect(selectQueueLength(root)).toBe(2);
    expect(selectIsLoading(root)).toBe(false);
    expect(selectError(root)).toBeNull();
  });

  it('selectCurrentQueueTrack returns null for empty queue', () => {
    const root = { queue: initialState };
    expect(selectCurrentQueueTrack(root as any)).toBeNull();
  });
});
