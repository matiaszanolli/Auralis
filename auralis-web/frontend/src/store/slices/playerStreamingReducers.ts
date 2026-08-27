/**
 * Player streaming sub-state reducers
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * The five reducers that write `player.streaming.{normal,enhanced}`, split out
 * of playerSlice's 369-line `reducers:` block (#5042) where they sat
 * interleaved with the flat player-state reducers they share nothing with.
 *
 * This splits the *file*, not the slice. RTK builds action types from the
 * slice name and the reducer key, so spreading this object into
 * `createSlice({ name: 'player', reducers: { ... } })` still produces
 * `player/startStreaming` and friends — no action-type string, store shape, or
 * DevTools entry changes, and no call site or test asserting on `.type` is
 * affected.
 *
 * Reducers are typed against `StreamingHostState` rather than `PlayerState`:
 * the full state type lives in playerSlice, and importing it here would make
 * the pair circular. Structurally it is the same object — `PlayerState`
 * satisfies this interface, so `createSlice` accepts these unchanged.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import type { PayloadAction } from '@reduxjs/toolkit';

export type StreamingState = 'idle' | 'buffering' | 'streaming' | 'error' | 'complete';

export type StreamType = 'normal' | 'enhanced';

export interface StreamingInfo {
  state: StreamingState;
  trackId: number | null;
  intensity: number;
  progress: number; // 0-100
  bufferedSamples: number;
  totalChunks: number;
  processedChunks: number;
  error: string | null;
}

/** The slice of player state these reducers touch. */
export interface StreamingHostState {
  lastUpdated: number;
  streaming: {
    normal: StreamingInfo;
    enhanced: StreamingInfo;
  };
}

export const initialStreamingInfo: StreamingInfo = {
  state: 'idle',
  trackId: null,
  intensity: 1.0,
  progress: 0,
  bufferedSamples: 0,
  totalChunks: 0,
  processedChunks: 0,
  error: null,
};

export const streamingReducers = {
  /**
   * Start audio streaming (normal or enhanced)
   */
  startStreaming: {
    reducer(
      state: StreamingHostState,
      action: PayloadAction<
        {
          streamType: StreamType;
          trackId: number;
          totalChunks: number;
          intensity: number;
        },
        string,
        { timestamp: number }
      >
    ) {
      const s = state.streaming[action.payload.streamType];
      s.state = 'buffering';
      s.trackId = action.payload.trackId;
      s.totalChunks = action.payload.totalChunks;
      s.intensity = action.payload.intensity;
      s.processedChunks = 0;
      s.progress = 0;
      s.bufferedSamples = 0;
      s.error = null;
      state.lastUpdated = action.meta.timestamp;
    },
    prepare(params: {
      streamType: StreamType;
      trackId: number;
      totalChunks: number;
      intensity: number;
    }) {
      return { payload: params, meta: { timestamp: Date.now() } };
    },
  },

  /**
   * Update streaming chunk progress
   */
  updateStreamingProgress: {
    reducer(
      state: StreamingHostState,
      action: PayloadAction<
        {
          streamType: StreamType;
          processedChunks: number;
          bufferedSamples: number;
          progress: number;
          /** When set, the update is ignored unless it matches the active stream's trackId (#4434). */
          trackId?: number;
        },
        string,
        { timestamp: number }
      >
    ) {
      const s = state.streaming[action.payload.streamType];
      // Drop late updates from a superseded track after a rapid skip (#4434).
      if (action.payload.trackId != null && s.trackId !== action.payload.trackId) return;
      s.processedChunks = action.payload.processedChunks;
      s.bufferedSamples = action.payload.bufferedSamples;
      s.progress = action.payload.progress;
      if (s.state === 'buffering' && action.payload.bufferedSamples > 0) {
        s.state = 'streaming';
      }
      state.lastUpdated = action.meta.timestamp;
    },
    prepare(params: {
      streamType: StreamType;
      processedChunks: number;
      bufferedSamples: number;
      progress: number;
      trackId?: number;
    }) {
      return { payload: params, meta: { timestamp: Date.now() } };
    },
  },

  /**
   * Mark streaming as complete
   */
  completeStreaming: {
    reducer(
      state: StreamingHostState,
      action: PayloadAction<{ streamType: StreamType; trackId?: number }, string, { timestamp: number }>
    ) {
      const s = state.streaming[action.payload.streamType];
      // Ignore a stale 'end' from a superseded track after a rapid skip (#4434).
      if (action.payload.trackId != null && s.trackId !== action.payload.trackId) return;
      s.state = 'complete';
      s.progress = 100;
      state.lastUpdated = action.meta.timestamp;
    },
    prepare(params: StreamType | { streamType: StreamType; trackId?: number }) {
      // Back-compat: accept a bare streamType or a { streamType, trackId } object.
      const payload = typeof params === 'string' ? { streamType: params } : params;
      return { payload, meta: { timestamp: Date.now() } };
    },
  },

  /**
   * Set streaming error
   */
  setStreamingError: {
    reducer(
      state: StreamingHostState,
      action: PayloadAction<{ streamType: StreamType; error: string; trackId?: number }, string, { timestamp: number }>
    ) {
      const s = state.streaming[action.payload.streamType];
      // Ignore a stale error from a superseded track after a rapid skip (#4434).
      if (action.payload.trackId != null && s.trackId !== action.payload.trackId) return;
      s.state = 'error';
      s.error = action.payload.error;
      state.lastUpdated = action.meta.timestamp;
    },
    prepare(params: { streamType: StreamType; error: string; trackId?: number }) {
      return { payload: params, meta: { timestamp: Date.now() } };
    },
  },

  /**
   * Reset streaming state
   */
  resetStreaming: {
    reducer(
      state: StreamingHostState,
      action: PayloadAction<{ streamType: StreamType }, string, { timestamp: number }>
    ) {
      state.streaming[action.payload.streamType] = { ...initialStreamingInfo };
      state.lastUpdated = action.meta.timestamp;
    },
    prepare(streamType: StreamType) {
      return { payload: { streamType }, meta: { timestamp: Date.now() } };
    },
  },
};
