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

export interface Track {
  id: number;
  title: string;
  artist: string;
  album?: string;
  duration: number;
  artworkUrl?: string;  // Standardized field name (was coverUrl)
}

export type PresetName = 'adaptive' | 'gentle' | 'warm' | 'bright' | 'punchy';

export type StreamingState = 'idle' | 'buffering' | 'streaming' | 'error' | 'complete';

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
  currentTrack: Track | null;
  currentTime: number;
  duration: number;
  volume: number;
  isMuted: boolean;
  preset: PresetName;
  isLoading: boolean;
  error: string | null;
  lastUpdated: number;
  streaming: StreamingInfo;
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
  volume: 70,
  isMuted: false,
  preset: 'adaptive',
  isLoading: false,
  error: null,
  lastUpdated: 0,
  streaming: initialStreamingInfo,
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
      reducer(state, action: PayloadAction<Track | null, string, { timestamp: number }>) {
        state.currentTrack = action.payload;
        if (action.payload) {
          state.duration = action.payload.duration;
          state.currentTime = 0;
        }
        state.lastUpdated = action.meta.timestamp;
      },
      prepare(track: Track | null) {
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
     * Set total duration
     */
    setDuration: {
      reducer(state, action: PayloadAction<number, string, { timestamp: number }>) {
        state.duration = action.payload;
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
     */
    clearError(state) {
      state.error = null;
    },

    /**
     * Update entire playback state (for WebSocket sync)
     */
    updatePlaybackState: {
      reducer(
        state,
        action: PayloadAction<
          Partial<Omit<PlayerState, 'lastUpdated'>>,
          string,
          { timestamp: number }
        >
      ) {
        Object.assign(state, action.payload);
        state.lastUpdated = action.meta.timestamp;
      },
      prepare(playbackState: Partial<Omit<PlayerState, 'lastUpdated'>>) {
        return { payload: playbackState, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Reset player state
     */
    resetPlayer(state) {
      Object.assign(state, initialState);
    },

    // ========================================================================
    // Streaming-specific reducers (Phase 2.2)
    // ========================================================================

    /**
     * Start enhanced audio streaming
     */
    startStreaming: {
      reducer(
        state,
        action: PayloadAction<
          {
            trackId: number;
            totalChunks: number;
            intensity: number;
          },
          string,
          { timestamp: number }
        >
      ) {
        state.streaming.state = 'buffering';
        state.streaming.trackId = action.payload.trackId;
        state.streaming.totalChunks = action.payload.totalChunks;
        state.streaming.intensity = action.payload.intensity;
        state.streaming.processedChunks = 0;
        state.streaming.progress = 0;
        state.streaming.bufferedSamples = 0;
        state.streaming.error = null;
        state.lastUpdated = action.meta.timestamp;
      },
      prepare(params: {
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
            processedChunks: number;
            bufferedSamples: number;
            progress: number;
          },
          string,
          { timestamp: number }
        >
      ) {
        state.streaming.processedChunks = action.payload.processedChunks;
        state.streaming.bufferedSamples = action.payload.bufferedSamples;
        state.streaming.progress = action.payload.progress;
        if (state.streaming.state === 'buffering' && action.payload.bufferedSamples > 0) {
          state.streaming.state = 'streaming';
        }
        state.lastUpdated = action.meta.timestamp;
      },
      prepare(params: {
        processedChunks: number;
        bufferedSamples: number;
        progress: number;
      }) {
        return { payload: params, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Mark streaming as complete
     */
    completeStreaming: {
      reducer(state, action: PayloadAction<undefined, string, { timestamp: number }>) {
        state.streaming.state = 'complete';
        state.streaming.progress = 100;
        state.lastUpdated = action.meta.timestamp;
      },
      prepare() {
        return { payload: undefined, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Set streaming error
     */
    setStreamingError: {
      reducer(state, action: PayloadAction<string, string, { timestamp: number }>) {
        state.streaming.state = 'error';
        state.streaming.error = action.payload;
        state.lastUpdated = action.meta.timestamp;
      },
      prepare(error: string) {
        return { payload: error, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Reset streaming state
     */
    resetStreaming: {
      reducer(state, action: PayloadAction<undefined, string, { timestamp: number }>) {
        state.streaming = initialStreamingInfo;
        state.lastUpdated = action.meta.timestamp;
      },
      prepare() {
        return { payload: undefined, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Update entire streaming info (for WebSocket sync)
     */
    updateStreamingInfo: {
      reducer(
        state,
        action: PayloadAction<
          Partial<Omit<StreamingInfo, 'error'>>,
          string,
          { timestamp: number }
        >
      ) {
        Object.assign(state.streaming, action.payload);
        state.lastUpdated = action.meta.timestamp;
      },
      prepare(streamingInfo: Partial<Omit<StreamingInfo, 'error'>>) {
        return { payload: streamingInfo, meta: { timestamp: Date.now() } };
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
  updatePlaybackState,
  resetPlayer,
  startStreaming,
  updateStreamingProgress,
  completeStreaming,
  setStreamingError,
  resetStreaming,
  updateStreamingInfo,
} = playerSlice.actions;

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
export const selectStreaming = (state: { player: PlayerState }) => state.player.streaming;
export const selectStreamingState = (state: { player: PlayerState }) => state.player.streaming.state;
export const selectStreamingProgress = (state: { player: PlayerState }) => state.player.streaming.progress;
export const selectStreamingTrackId = (state: { player: PlayerState }) => state.player.streaming.trackId;
export const selectStreamingIntensity = (state: { player: PlayerState }) => state.player.streaming.intensity;
export const selectBufferedSamples = (state: { player: PlayerState }) => state.player.streaming.bufferedSamples;
export const selectStreamingError = (state: { player: PlayerState }) => state.player.streaming.error;
export const selectIsStreaming = (state: { player: PlayerState }) =>
  state.player.streaming.state === 'streaming' || state.player.streaming.state === 'buffering';

export default playerSlice.reducer;
