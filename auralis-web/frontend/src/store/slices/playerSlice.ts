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
 * @license AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
 */

import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import type { EnhancementPreset, PlayerTrack } from '@/types/domain';
import { initialStreamingInfo, streamingReducers } from './playerStreamingReducers';
import type { StreamingInfo } from './playerStreamingReducers';

// Re-exported so the slice stays the single import site for player state types.
export type { StreamingState, StreamType, StreamingInfo } from './playerStreamingReducers';

// Derived from the canonical EnhancementPreset, not redeclared (#5610) --
// a hand-mirrored literal here could drift from types/domain.ts.
export type PresetName = EnhancementPreset;

export interface PlayerState {
  isPlaying: boolean;
  currentTrack: PlayerTrack | null;
  currentTime: number;
  duration: number;
  volume: number;
  isMuted: boolean;
  preset: PresetName;
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
        } else {
          // #5623: clearing the track must clear its times too, or
          // selectPlaybackProgress/selectFormattedTime keep reporting the
          // previous track's progress after a queue clear. The snapshot's own
          // duration/current_time fields (dispatched after this by
          // usePlayerStateSync) still overwrite both when present.
          state.duration = 0;
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
  resetPlayer,
  startStreaming,
  updateStreamingProgress,
  completeStreaming,
  setStreamingError,
  resetStreaming,
  setPlaybackStalled,
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

// #5354: selectIsLoading/selectError and the isLoading/error state they read
// were deleted — no production code ever dispatched the actions that would
// change them, so they could never leave their initial values.

/**
 * Convert Redux player volume/mute into the AudioPlaybackEngine gain (0-1)
 * (#5607). Redux is 0-100 (#2251), the engine is 0-1 (#2116), and mute is
 * gain 0. Single source so every apply-point — engine construction and the
 * Redux subscription — converts identically.
 */
export function engineGainFromPlayerState(player: {
  volume: number;
  isMuted: boolean;
}): number {
  return player.isMuted ? 0 : Math.max(0, Math.min(1, player.volume / 100));
}

// Streaming selectors (Phase 2.2)
//
// #5211: nine of the eleven selectors that used to live here had zero
// references anywhere, tests included. They duplicated a layer that already
// exists — `store/selectors/player.ts` carries the canonical `selectStreaming`
// / `selectEnhancedStreamingState` — so nothing ever reached for these.
// Real readers of raw streaming state (useAudioVisualization.ts,
// usePlayEnhanced.ts) read `state.player.streaming.enhanced` directly via
// this selector -- the #5211 comment that used to stand here named
// hooks/enhancement/useEnhancedPlaybackShortcuts.ts as "the one production
// reader", which was already wrong when written (it was never actually
// called anywhere, and has since been deleted entirely -- #4861 follow-up).
//
// Only the selector with a real consumer is kept.
export const selectEnhancedStreaming = (state: { player: PlayerState }) => state.player.streaming.enhanced;

export default playerSlice.reducer;
