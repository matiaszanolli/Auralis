/**
 * Queue State Slice
 * ~~~~~~~~~~~~~~~~~
 *
 * Redux slice for managing audio queue state including:
 * - Queue tracks
 * - Current queue position
 * - Queue operations (add, remove, reorder)
 *
 * Phase C.3: Component Testing & Integration
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import type { Track } from './playerSlice';

export interface QueueState {
  tracks: Track[];
  currentIndex: number;
  isLoading: boolean;
  error: string | null;
  lastUpdated: number;
}

const initialState: QueueState = {
  tracks: [],
  currentIndex: 0,
  isLoading: false,
  error: null,
  lastUpdated: 0,
};

const queueSlice = createSlice({
  name: 'queue',
  initialState,
  reducers: {
    /**
     * Add track to queue
     */
    addTrack: {
      reducer(state, action: PayloadAction<Track, string, { timestamp: number }>) {
        state.tracks.push(action.payload);
        state.lastUpdated = action.meta.timestamp;
      },
      prepare(track: Track) {
        return { payload: track, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Add multiple tracks to queue
     */
    addTracks: {
      reducer(state, action: PayloadAction<Track[], string, { timestamp: number }>) {
        state.tracks.push(...action.payload);
        state.lastUpdated = action.meta.timestamp;
      },
      prepare(tracks: Track[]) {
        return { payload: tracks, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Remove track from queue by index
     */
    removeTrack: {
      reducer(state, action: PayloadAction<number, string, { timestamp: number }>) {
        const index = action.payload;
        if (index >= 0 && index < state.tracks.length) {
          state.tracks.splice(index, 1);
          // Adjust currentIndex if needed
          if (index < state.currentIndex) {
            state.currentIndex = Math.max(0, state.currentIndex - 1);
          } else if (index === state.currentIndex && state.currentIndex >= state.tracks.length) {
            state.currentIndex = Math.max(0, state.currentIndex - 1);
          }
          state.lastUpdated = action.meta.timestamp;
        }
      },
      prepare(index: number) {
        return { payload: index, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Reorder track in queue
     */
    reorderTrack: {
      reducer(
        state,
        action: PayloadAction<{ fromIndex: number; toIndex: number }, string, { timestamp: number }>
      ) {
        const { fromIndex, toIndex } = action.payload;
        if (fromIndex === toIndex) return;

        const [movedTrack] = state.tracks.splice(fromIndex, 1);
        state.tracks.splice(toIndex, 0, movedTrack);

        // Update currentIndex
        if (state.currentIndex === fromIndex) {
          state.currentIndex = toIndex;
        } else if (fromIndex < state.currentIndex && toIndex >= state.currentIndex) {
          state.currentIndex = Math.max(0, state.currentIndex - 1);
        } else if (fromIndex > state.currentIndex && toIndex <= state.currentIndex) {
          state.currentIndex = Math.min(state.tracks.length - 1, state.currentIndex + 1);
        }

        state.lastUpdated = action.meta.timestamp;
      },
      prepare(payload: { fromIndex: number; toIndex: number }) {
        return { payload, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Clear entire queue
     */
    clearQueue: {
      reducer(state, action: PayloadAction<void, string, { timestamp: number }>) {
        state.tracks = [];
        state.currentIndex = 0;
        state.lastUpdated = action.meta.timestamp;
      },
      prepare() {
        return { payload: undefined, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Set entire queue
     */
    setQueue: {
      reducer(state, action: PayloadAction<Track[], string, { timestamp: number }>) {
        state.tracks = action.payload;
        state.currentIndex = Math.min(state.currentIndex, state.tracks.length - 1);
        state.lastUpdated = action.meta.timestamp;
      },
      prepare(tracks: Track[]) {
        return { payload: tracks, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Set current queue index
     */
    setCurrentIndex: {
      reducer(state, action: PayloadAction<number, string, { timestamp: number }>) {
        const index = action.payload;
        if (index >= 0 && index < state.tracks.length) {
          state.currentIndex = index;
          state.lastUpdated = action.meta.timestamp;
        }
      },
      prepare(index: number) {
        return { payload: index, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Go to next track
     */
    nextTrack: {
      reducer(state, action: PayloadAction<void, string, { timestamp: number }>) {
        if (state.currentIndex < state.tracks.length - 1) {
          state.currentIndex += 1;
          state.lastUpdated = action.meta.timestamp;
        }
      },
      prepare() {
        return { payload: undefined, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Go to previous track
     */
    previousTrack: {
      reducer(state, action: PayloadAction<void, string, { timestamp: number }>) {
        if (state.currentIndex > 0) {
          state.currentIndex -= 1;
          state.lastUpdated = action.meta.timestamp;
        }
      },
      prepare() {
        return { payload: undefined, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Set loading state
     */
    setIsLoading: {
      reducer(state, action: PayloadAction<boolean, string, { timestamp: number }>) {
        state.isLoading = action.payload;
        state.lastUpdated = action.meta.timestamp;
      },
      prepare(isLoading: boolean) {
        return { payload: isLoading, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Set error message
     */
    setError: {
      reducer(state, action: PayloadAction<string | null, string, { timestamp: number }>) {
        state.error = action.payload;
        state.lastUpdated = action.meta.timestamp;
      },
      prepare(error: string | null) {
        return { payload: error, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Clear error
     */
    clearError(state) {
      state.error = null;
    },

    /**
     * Reset queue state
     */
    resetQueue(state) {
      Object.assign(state, initialState);
    },
  },
});

export const {
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
} = queueSlice.actions;

// Selectors
export const selectQueueTracks = (state: { queue: QueueState }) => state.queue.tracks;
export const selectCurrentIndex = (state: { queue: QueueState }) => state.queue.currentIndex;
export const selectCurrentQueueTrack = (state: { queue: QueueState }) =>
  state.queue.tracks[state.queue.currentIndex] || null;
export const selectQueueLength = (state: { queue: QueueState }) => state.queue.tracks.length;
export const selectIsLoading = (state: { queue: QueueState }) => state.queue.isLoading;
export const selectError = (state: { queue: QueueState }) => state.queue.error;
export const selectQueueState = (state: { queue: QueueState }) => state.queue;

/**
 * Calculate total remaining time in queue from current index
 */
export const selectRemainingTime = (state: { queue: QueueState }) => {
  return state.queue.tracks
    .slice(state.queue.currentIndex + 1)
    .reduce((sum, track) => sum + track.duration, 0);
};

/**
 * Calculate total queue duration
 */
export const selectTotalQueueTime = (state: { queue: QueueState }) => {
  return state.queue.tracks.reduce((sum, track) => sum + track.duration, 0);
};

export default queueSlice.reducer;
