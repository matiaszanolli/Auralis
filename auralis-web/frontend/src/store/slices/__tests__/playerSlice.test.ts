/**
 * playerSlice reducer unit tests (#2367)
 *
 * Covers all action creators and streaming state machine transitions.
 */

import reducer, {
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
} from '../playerSlice';
import type { PlayerState, Track } from '../playerSlice';

const initialState: PlayerState = {
  isPlaying: false,
  currentTrack: null,
  currentTime: 0,
  duration: 0,
  volume: 80,
  isMuted: false,
  preset: 'adaptive',
  isLoading: false,
  error: null,
  lastUpdated: 0,
  streaming: {
    normal: {
      state: 'idle',
      trackId: null,
      intensity: 1.0,
      progress: 0,
      bufferedSamples: 0,
      totalChunks: 0,
      processedChunks: 0,
      error: null,
    },
    enhanced: {
      state: 'idle',
      trackId: null,
      intensity: 1.0,
      progress: 0,
      bufferedSamples: 0,
      totalChunks: 0,
      processedChunks: 0,
      error: null,
    },
  },
};

const mockTrack: Track = {
  id: 1,
  title: 'Test Track',
  artist: 'Test Artist',
  album: 'Test Album',
  duration: 240,
};

describe('playerSlice', () => {
  it('should return initial state', () => {
    const state = reducer(undefined, { type: 'unknown' });
    expect(state.isPlaying).toBe(false);
    expect(state.volume).toBe(80);
    expect(state.preset).toBe('adaptive');
    expect(state.streaming.normal.state).toBe('idle');
    expect(state.streaming.enhanced.state).toBe('idle');
  });

  // ─── Playback reducers ──────────────────────────────────────────

  it('setIsPlaying sets playing state and timestamp', () => {
    const state = reducer(initialState, setIsPlaying(true));
    expect(state.isPlaying).toBe(true);
    expect(state.lastUpdated).toBeGreaterThan(0);
  });

  it('setCurrentTrack resets currentTime and sets duration', () => {
    const state = reducer(initialState, setCurrentTrack(mockTrack));
    expect(state.currentTrack).toEqual(mockTrack);
    expect(state.duration).toBe(240);
    expect(state.currentTime).toBe(0);
  });

  it('setCurrentTrack with null clears track', () => {
    const playing = reducer(initialState, setCurrentTrack(mockTrack));
    const state = reducer(playing, setCurrentTrack(null));
    expect(state.currentTrack).toBeNull();
  });

  it('setCurrentTime clamps to duration', () => {
    let state = reducer(initialState, setDuration(100));
    state = reducer(state, setCurrentTime(150));
    expect(state.currentTime).toBe(100);
  });

  it('setDuration updates duration', () => {
    const state = reducer(initialState, setDuration(300));
    expect(state.duration).toBe(300);
  });

  // ─── Volume reducers ───────────────────────────────────────────

  it('setVolume clamps 0-100 and unmutes', () => {
    let state = reducer(initialState, setMuted(true));
    state = reducer(state, setVolume(50));
    expect(state.volume).toBe(50);
    expect(state.isMuted).toBe(false);
  });

  it('setVolume clamps below 0', () => {
    const state = reducer(initialState, setVolume(-10));
    expect(state.volume).toBe(0);
  });

  it('setVolume clamps above 100', () => {
    const state = reducer(initialState, setVolume(150));
    expect(state.volume).toBe(100);
  });

  it('toggleMute toggles muted state', () => {
    let state = reducer(initialState, toggleMute());
    expect(state.isMuted).toBe(true);
    state = reducer(state, toggleMute());
    expect(state.isMuted).toBe(false);
  });

  it('setMuted sets muted explicitly', () => {
    const state = reducer(initialState, setMuted(true));
    expect(state.isMuted).toBe(true);
  });

  // ─── Preset / loading / error ──────────────────────────────────

  it('setPreset changes preset', () => {
    const state = reducer(initialState, setPreset('warm'));
    expect(state.preset).toBe('warm');
  });

  it('setIsLoading sets loading', () => {
    const state = reducer(initialState, setIsLoading(true));
    expect(state.isLoading).toBe(true);
  });

  it('setError and clearError manage error state', () => {
    let state = reducer(initialState, setError('Something broke'));
    expect(state.error).toBe('Something broke');
    state = reducer(state, clearError());
    expect(state.error).toBeNull();
  });

  // ─── updatePlaybackState (deep merge) ─────────────────────────

  it('updatePlaybackState deep-merges streaming sub-state (#2352)', () => {
    // Start enhanced streaming
    let state = reducer(
      initialState,
      startStreaming({
        streamType: 'enhanced',
        trackId: 1,
        totalChunks: 10,
        intensity: 0.8,
      }),
    );

    // Update progress
    state = reducer(
      state,
      updateStreamingProgress({
        streamType: 'enhanced',
        processedChunks: 5,
        bufferedSamples: 44100,
        progress: 50,
      }),
    );

    // Simulate a server sync that only sends partial state (no streaming)
    state = reducer(state, updatePlaybackState({ isPlaying: true }));

    // Streaming sub-state must NOT be clobbered
    expect(state.isPlaying).toBe(true);
    expect(state.streaming.enhanced.processedChunks).toBe(5);
    expect(state.streaming.enhanced.progress).toBe(50);
  });

  // ─── resetPlayer ──────────────────────────────────────────────

  it('resetPlayer returns to initial state', () => {
    let state = reducer(initialState, setIsPlaying(true));
    state = reducer(state, setVolume(42));
    state = reducer(state, resetPlayer());
    expect(state.isPlaying).toBe(false);
    expect(state.volume).toBe(80);
    expect(state.streaming.enhanced.state).toBe('idle');
  });

  // ─── Streaming state machine ──────────────────────────────────

  describe('streaming state machine', () => {
    it('startStreaming transitions to buffering', () => {
      const state = reducer(
        initialState,
        startStreaming({
          streamType: 'enhanced',
          trackId: 42,
          totalChunks: 10,
          intensity: 0.9,
        }),
      );
      const s = state.streaming.enhanced;
      expect(s.state).toBe('buffering');
      expect(s.trackId).toBe(42);
      expect(s.totalChunks).toBe(10);
      expect(s.intensity).toBe(0.9);
      expect(s.processedChunks).toBe(0);
      expect(s.progress).toBe(0);
      expect(s.error).toBeNull();
    });

    it('updateStreamingProgress transitions buffering → streaming', () => {
      let state = reducer(
        initialState,
        startStreaming({ streamType: 'normal', trackId: 1, totalChunks: 5, intensity: 1 }),
      );
      state = reducer(
        state,
        updateStreamingProgress({
          streamType: 'normal',
          processedChunks: 1,
          bufferedSamples: 8820,
          progress: 20,
        }),
      );
      expect(state.streaming.normal.state).toBe('streaming');
      expect(state.streaming.normal.processedChunks).toBe(1);
      expect(state.streaming.normal.bufferedSamples).toBe(8820);
      expect(state.streaming.normal.progress).toBe(20);
    });

    it('completeStreaming sets state=complete and progress=100', () => {
      let state = reducer(
        initialState,
        startStreaming({ streamType: 'enhanced', trackId: 1, totalChunks: 3, intensity: 1 }),
      );
      state = reducer(state, completeStreaming('enhanced'));
      expect(state.streaming.enhanced.state).toBe('complete');
      expect(state.streaming.enhanced.progress).toBe(100);
    });

    it('setStreamingError sets state=error with message', () => {
      let state = reducer(
        initialState,
        startStreaming({ streamType: 'enhanced', trackId: 1, totalChunks: 3, intensity: 1 }),
      );
      state = reducer(
        state,
        setStreamingError({ streamType: 'enhanced', error: 'Decode failed' }),
      );
      expect(state.streaming.enhanced.state).toBe('error');
      expect(state.streaming.enhanced.error).toBe('Decode failed');
    });

    it('resetStreaming clears all sub-fields', () => {
      let state = reducer(
        initialState,
        startStreaming({ streamType: 'normal', trackId: 99, totalChunks: 8, intensity: 0.5 }),
      );
      state = reducer(state, resetStreaming('normal'));
      expect(state.streaming.normal.state).toBe('idle');
      expect(state.streaming.normal.trackId).toBeNull();
      expect(state.streaming.normal.totalChunks).toBe(0);
      expect(state.streaming.normal.processedChunks).toBe(0);
    });

    it('updateStreamingInfo partial-merges into sub-state', () => {
      let state = reducer(
        initialState,
        startStreaming({ streamType: 'enhanced', trackId: 1, totalChunks: 10, intensity: 1 }),
      );
      state = reducer(
        state,
        updateStreamingInfo({ streamType: 'enhanced', progress: 75, bufferedSamples: 100000 }),
      );
      // Merged fields
      expect(state.streaming.enhanced.progress).toBe(75);
      expect(state.streaming.enhanced.bufferedSamples).toBe(100000);
      // Unchanged fields
      expect(state.streaming.enhanced.trackId).toBe(1);
      expect(state.streaming.enhanced.totalChunks).toBe(10);
    });

    it('normal and enhanced streams are independent', () => {
      let state = reducer(
        initialState,
        startStreaming({ streamType: 'normal', trackId: 1, totalChunks: 5, intensity: 1 }),
      );
      state = reducer(
        state,
        startStreaming({ streamType: 'enhanced', trackId: 2, totalChunks: 8, intensity: 0.7 }),
      );
      expect(state.streaming.normal.trackId).toBe(1);
      expect(state.streaming.enhanced.trackId).toBe(2);

      state = reducer(state, resetStreaming('normal'));
      expect(state.streaming.normal.state).toBe('idle');
      expect(state.streaming.enhanced.state).toBe('buffering');
    });
  });
});
