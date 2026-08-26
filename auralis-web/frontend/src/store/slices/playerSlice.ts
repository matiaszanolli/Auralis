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
import { setCurrentIndex, updateTrackById } from '@/store/slices/queueSlice';

export type PresetName = 'adaptive' | 'gentle' | 'warm' | 'bright' | 'punchy';

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

const initialStreamingInfo: StreamingInfo = {
  state: 'idle',
  trackId: null,
  intensity: 1.0,
  progress: 0,
  bufferedSamples: 0,
  totalChunks: 0,
  processedChunks: 0,
  error: null,
};

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
    startStreaming: {
      reducer(
        state,
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
        state,
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
        state,
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
        state,
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
      reducer(state, action: PayloadAction<{ streamType: StreamType }, string, { timestamp: number }>) {
        state.streaming[action.payload.streamType] = { ...initialStreamingInfo };
        state.lastUpdated = action.meta.timestamp;
      },
      prepare(streamType: StreamType) {
        return { payload: { streamType }, meta: { timestamp: Date.now() } };
      },
    },

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

/**
 * #3587: dispatch `setCurrentTrack(track)` AND align `queue.currentIndex`
 * to the track's position in the queue (when it is present). Local
 * track-change paths (usePlayNormal, usePlayEnhanced, Player.next/prev)
 * previously updated only `player.currentTrack`, leaving consumers of
 * `selectCurrentQueueTrack` out of sync until the backend WebSocket
 * `player_state` confirmation arrived — or permanently, if it never did.
 *
 * If the track is not in the queue (e.g. ad-hoc play), the queue index
 * stays put and the desync window is moot (no queue-derived selector
 * matches anyway).
 */
export const setCurrentTrackAndSyncQueue =
  (track: PlayerTrack | null) =>
  (
    dispatch: (action: unknown) => unknown,
    getState: () => { queue?: { tracks: { id: number }[] } },
  ) => {
    dispatch(setCurrentTrack(track));
    if (track == null) return;
    const queue = getState().queue;
    if (!queue?.tracks?.length) return;
    const idx = queue.tracks.findIndex((t) => t.id === track.id);
    if (idx >= 0) {
      dispatch(setCurrentIndex(idx));
    }
  };

/**
 * #4580: dispatch `setDuration(duration)` AND patch the queue's copy of the
 * same track.
 *
 * `player.currentTrack` and `queue.tracks[currentIndex]` are two independent
 * records of the same fact. `setDuration` can only reach the player copy, so a
 * `player_state` snapshot carrying a re-analysed duration without a fresh
 * queue array left `selectRemainingTime` / `selectTotalQueueTime` / the queue
 * rows showing the pre-correction value indefinitely.
 *
 * Same shape as `setCurrentTrackAndSyncQueue` (#3587), which exists for the
 * same reason: the two slices must be moved together by the caller, because
 * neither reducer can see the other's state.
 *
 * Note this is a *duration* sync specifically. `artworkUrl` is the other field
 * that could in principle drift, but nothing patches it post-hoc today —
 * artwork refreshes go through a per-album version counter
 * (`useArtworkUpdates`), not through these track records — so there is no
 * one-sided write to mirror. `updateTrackById` takes a generic `changes` patch
 * so covering it later needs no new plumbing.
 */
export const setDurationAndSyncQueue =
  (duration: number) =>
  (
    dispatch: (action: unknown) => unknown,
    getState: () => { player?: { currentTrack?: { id: number } | null } },
  ) => {
    dispatch(setDuration(duration));
    const trackId = getState().player?.currentTrack?.id;
    if (trackId == null) return;
    dispatch(updateTrackById({ id: trackId, changes: { duration } }));
  };

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
