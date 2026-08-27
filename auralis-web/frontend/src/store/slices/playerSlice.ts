/**
 * Player State Slice
 * ~~~~~~~~~~~~~~~~~~
 *
 * Redux slice for managing player state including:
 * - Playback state (playing, paused, loading)
 * - Current track and time
 * - Volume and mute
 * - Audio preset
 *
 * Phase C.3: Component Testing & Integration
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import type { PlayerTrack } from '@/types/domain';
import { initialStreamingInfo, streamingReducers } from './playerStreamingReducers';
import type { StreamingInfo } from './playerStreamingReducers';

// Re-exported so the slice stays the single import site for player state types.
export type { StreamingState, StreamType, StreamingInfo } from './playerStreamingReducers';

export type PresetName = 'adaptive' | 'gentle' | 'warm' | 'bright' | 'punchy';

export interface PlayerState {
  isPlaying: boolean;
  currentTrack: PlayerTrack | null;
  currentTime: number;
  duration: number;
  volume: number;
  isMuted: boolean;
  preset: PresetName;
  isLoading: boolean;
  error: string | null;
  lastUpdated: number;
  streaming: {
    normal: StreamingInfo;
    enhanced: StreamingInfo;
  };
}

const initialState: PlayerState = {
  isPlaying: false,
  currentTrack: null,
  currentTime: 0,
  duration: 0,
  volume: 80,  // matches backend PlayerState default (issue #2251)
  isMuted: false,
  preset: 'adaptive',
  isLoading: false,
  error: null,
  lastUpdated: 0,
  streaming: {
    normal: { ...initialStreamingInfo },
    enhanced: { ...initialStreamingInfo },
  },
};

const playerSlice = createSlice({
  name: 'player',
  initialState,
  reducers: {
    /**
     * Set playing state
     */
    setIsPlaying: {
      reducer(state, action: PayloadAction<boolean, string, { timestamp: number }>) {
        state.isPlaying = action.payload;
        state.lastUpdated = action.meta.timestamp;
      },
      prepare(isPlaying: boolean) {
        return { payload: isPlaying, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Set current track
     */
    setCurrentTrack: {
      reducer(state, action: PayloadAction<PlayerTrack | null, string, { timestamp: number }>) {
        state.currentTrack = action.payload;
        if (action.payload) {
          state.duration = action.payload.duration;
          state.currentTime = 0;
        }
        state.lastUpdated = action.meta.timestamp;
      },
      prepare(track: PlayerTrack | null) {
        return { payload: track, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Set current playback time
     */
    setCurrentTime: {
      reducer(state, action: PayloadAction<number, string, { timestamp: number }>) {
        state.currentTime = Math.min(action.payload, state.duration);
        state.lastUpdated = action.meta.timestamp;
      },
      prepare(time: number) {
        return { payload: time, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Set total duration.
     * Syncs to currentTrack.duration to prevent divergence (#2774).
     */
    setDuration: {
      reducer(state, action: PayloadAction<number, string, { timestamp: number }>) {
        state.duration = action.payload;
        // Re-clamp currentTime: a shorter re-analysed duration would otherwise
        // leave currentTime > duration (#4191).
        if (state.currentTime > action.payload) {
          state.currentTime = action.payload;
        }
        if (state.currentTrack) {
          state.currentTrack.duration = action.payload;
        }
        state.lastUpdated = action.meta.timestamp;
      },
      prepare(duration: number) {
        return { payload: duration, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Set volume (0-100)
     */
    setVolume: {
      reducer(state, action: PayloadAction<number, string, { timestamp: number }>) {
        state.volume = Math.max(0, Math.min(100, action.payload));
        if (state.volume > 0) {
          state.isMuted = false;
        }
        state.lastUpdated = action.meta.timestamp;
      },
      prepare(volume: number) {
        return { payload: volume, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Toggle mute
     */
    toggleMute: {
      reducer(state, action: PayloadAction<undefined, string, { timestamp: number }>) {
        state.isMuted = !state.isMuted;
        state.lastUpdated = action.meta.timestamp;
      },
      prepare() {
        return { payload: undefined, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Set mute state
     */
    setMuted: {
      reducer(state, action: PayloadAction<boolean, string, { timestamp: number }>) {
        state.isMuted = action.payload;
        state.lastUpdated = action.meta.timestamp;
      },
      prepare(isMuted: boolean) {
        return { payload: isMuted, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Set audio preset
     */
    setPreset: {
      reducer(state, action: PayloadAction<PresetName, string, { timestamp: number }>) {
        state.preset = action.payload;
        state.lastUpdated = action.meta.timestamp;
      },
      prepare(preset: PresetName) {
        return { payload: preset, meta: { timestamp: Date.now() } };
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
     *
     * No production dispatch sites (#4921) for THIS slice; cacheSlice's and
     * connectionSlice's same-named actions ARE dispatched, from useReduxState.ts — kept as an idiomatic
     * Redux action. Live sync uses field-level dispatches; see the note on
     * resetPlayer in playerSlice.ts for why the bulk-update siblings were
     * deleted rather than documented.
     */
    clearError(state) {
      state.error = null;
    },

    /**
     * Reset player state
     *
     * No production dispatch sites (#4921) — kept as a store-reset helper, which components/__tests__/Integration.test.tsx:425 uses. Live WebSocket sync
     * dispatches field-level actions from usePlayerStateSync.ts /
     * useAPIHealthPoll.ts, which is the intended architecture; the bulk
     * updatePlaybackState/updateStreamingInfo/updateConnectionState actions
     * that sat beside these were deleted in #4921 because they duplicated
     * hardening the field-level path already has.
     */
    resetPlayer(state) {
      Object.assign(state, {
        ...initialState,
        streaming: {
          normal: { ...initialStreamingInfo },
          enhanced: { ...initialStreamingInfo },
        },
      });
    },

    // ========================================================================
    // Streaming-specific reducers (Phase 2.2)
    // ========================================================================

    /**
     * Start audio streaming (normal or enhanced)
     */
    // Streaming sub-state reducers live in ./playerStreamingReducers (#5042).
    // Spreading rather than nesting keeps the action types identical
    // (`player/startStreaming`, ...), so no dispatcher or `.type` assertion
    // changes.
    ...streamingReducers,
  },
});

export const {
  setIsPlaying,
  setCurrentTrack,
  setCurrentTime,
  setDuration,
  setVolume,
  toggleMute,
  setMuted,
  setPreset,
  setIsLoading,
  setError,
  clearError,
  resetPlayer,
  startStreaming,
  updateStreamingProgress,
  completeStreaming,
  setStreamingError,
  resetStreaming,
} = playerSlice.actions;

// The setCurrentTrackAndSyncQueue / setDurationAndSyncQueue thunks moved to
// ./playerQueueSync (#5042) — they synchronise two slices rather than reducing
// player state, and importing queueSlice's actions here only served them.

// Selectors
export const selectIsPlaying = (state: { player: PlayerState }) => state.player.isPlaying;
export const selectCurrentTrack = (state: { player: PlayerState }) => state.player.currentTrack;
export const selectCurrentTime = (state: { player: PlayerState }) => state.player.currentTime;
export const selectDuration = (state: { player: PlayerState }) => state.player.duration;
export const selectVolume = (state: { player: PlayerState }) => state.player.volume;
export const selectIsMuted = (state: { player: PlayerState }) => state.player.isMuted;
export const selectPreset = (state: { player: PlayerState }) => state.player.preset;
export const selectIsLoading = (state: { player: PlayerState }) => state.player.isLoading;
export const selectError = (state: { player: PlayerState }) => state.player.error;
export const selectPlayerState = (state: { player: PlayerState }) => state.player;

// Streaming selectors (Phase 2.2)
//
// #5211: nine of the eleven selectors that used to live here had zero
// references anywhere, tests included. They duplicated a layer that already
// exists — `store/selectors/player.ts` carries the canonical `selectStreaming`
// / `selectEnhancedStreamingState` — so nothing ever reached for these, and
// the one production reader that wants raw streaming state
// (hooks/enhancement/useEnhancedPlaybackShortcuts.ts) reads
// `state.player.streaming.enhanced` directly.
//
// Only the selector with a real consumer is kept.
export const selectEnhancedStreaming = (state: { player: PlayerState }) => state.player.streaming.enhanced;

export default playerSlice.reducer;
