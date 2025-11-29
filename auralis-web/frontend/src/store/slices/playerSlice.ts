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
  coverUrl?: string;
}

export type PresetName = 'adaptive' | 'gentle' | 'warm' | 'bright' | 'punchy';

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
}

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
};

const playerSlice = createSlice({
  name: 'player',
  initialState,
  reducers: {
    /**
     * Set playing state
     */
    setIsPlaying(state, action: PayloadAction<boolean>) {
      state.isPlaying = action.payload;
      state.lastUpdated = Date.now();
    },

    /**
     * Set current track
     */
    setCurrentTrack(state, action: PayloadAction<Track | null>) {
      state.currentTrack = action.payload;
      if (action.payload) {
        state.duration = action.payload.duration;
        state.currentTime = 0;
      }
      state.lastUpdated = Date.now();
    },

    /**
     * Set current playback time
     */
    setCurrentTime(state, action: PayloadAction<number>) {
      state.currentTime = Math.min(action.payload, state.duration);
      state.lastUpdated = Date.now();
    },

    /**
     * Set total duration
     */
    setDuration(state, action: PayloadAction<number>) {
      state.duration = action.payload;
      state.lastUpdated = Date.now();
    },

    /**
     * Set volume (0-100)
     */
    setVolume(state, action: PayloadAction<number>) {
      state.volume = Math.max(0, Math.min(100, action.payload));
      if (state.volume > 0) {
        state.isMuted = false;
      }
      state.lastUpdated = Date.now();
    },

    /**
     * Toggle mute
     */
    toggleMute(state) {
      state.isMuted = !state.isMuted;
      state.lastUpdated = Date.now();
    },

    /**
     * Set mute state
     */
    setMuted(state, action: PayloadAction<boolean>) {
      state.isMuted = action.payload;
      state.lastUpdated = Date.now();
    },

    /**
     * Set audio preset
     */
    setPreset(state, action: PayloadAction<PresetName>) {
      state.preset = action.payload;
      state.lastUpdated = Date.now();
    },

    /**
     * Set loading state
     */
    setIsLoading(state, action: PayloadAction<boolean>) {
      state.isLoading = action.payload;
      state.lastUpdated = Date.now();
    },

    /**
     * Set error message
     */
    setError(state, action: PayloadAction<string | null>) {
      state.error = action.payload;
      state.lastUpdated = Date.now();
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
    updatePlaybackState(
      state,
      action: PayloadAction<Partial<Omit<PlayerState, 'lastUpdated'>>>
    ) {
      Object.assign(state, action.payload);
      state.lastUpdated = Date.now();
    },

    /**
     * Reset player state
     */
    resetPlayer(state) {
      Object.assign(state, initialState);
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

export default playerSlice.reducer;
