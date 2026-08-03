/**
 * PlaybackSessionContext - single shared enhanced-audio streaming session
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * #4541: `usePlayEnhanced()` owns hook-instance-local state (AudioContext,
 * PCM buffer, playback engine refs) — calling it more than once creates
 * independent streaming sessions that don't share state. Player.tsx and the
 * global keyboard shortcuts (ComfortableApp) each called their own control
 * plane, so pressing Space sent a WS `play_normal` command that cancelled
 * the session Player.tsx had actually started.
 *
 * This provider calls `usePlayEnhanced()` exactly once at the app root and
 * exposes the transport handlers (play/pause, next/previous, volume/mute,
 * seek) that both Player.tsx's transport bar and the global shortcuts
 * consume via `usePlaybackSession()`.
 *
 * @module contexts/PlaybackSessionContext
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, type ReactNode } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import type { AppDispatch } from '@/store';
import { usePlayEnhanced } from '@/hooks/enhancement/usePlayEnhanced';
import { useEnhancementControl } from '@/hooks/enhancement/useEnhancementControl';
import { selectQueueTracks, selectCurrentIndex } from '@/store/slices/queueSlice';
import { setCurrentTrackAndSyncQueue, setVolume as setVolumeAction } from '@/store/slices/playerSlice';
import { playerSelectors } from '@/store/selectors';

const DEBUG = import.meta.env.DEV;

interface PlaybackSessionContextValue {
  /** True while a chunk is streaming or buffering. */
  isStreaming: boolean;
  /** Streaming state machine (idle, buffering, streaming, error, complete). */
  streamingState: 'idle' | 'buffering' | 'streaming' | 'error' | 'complete';
  processedChunks: number;
  totalChunks: number;
  /** Current playback position (seconds) reported by the streaming engine. */
  currentTime: number;
  isPaused: boolean;
  isSeeking: boolean;
  error: string | null;

  /** Start a track using the current enhancement enabled/preset/intensity state. */
  startTrack: (trackId: number) => Promise<void>;

  /** Seek to a position (seconds) in the current track. */
  handleSeek: (position: number) => void;
  /** Play/pause/resume the current track — the single entry point for both
   *  the transport bar and the Space shortcut. */
  handlePlayPause: () => Promise<void>;
  /** Stop current playback and play the next queue track. */
  handleNext: () => Promise<void>;
  /** Stop current playback and play the previous queue track. */
  handlePrevious: () => Promise<void>;
  /** Set the live playback volume (0-1) and persist it to Redux. */
  handleVolumeChange: (volume: number) => Promise<void>;
  /** Toggle mute, restoring the pre-mute volume on unmute. Returns the
   *  resulting muted state so callers can report it (e.g. a toast). */
  handleMuteToggle: () => Promise<boolean>;
}

const PlaybackSessionContext = createContext<PlaybackSessionContextValue | null>(null);

export function PlaybackSessionProvider({ children }: { children: ReactNode }) {
  const dispatch = useDispatch<AppDispatch>();

  const currentTrack = useSelector(playerSelectors.selectCurrentTrack);
  const playerVolume = useSelector(playerSelectors.selectVolume);
  const playerIsMuted = useSelector(playerSelectors.selectIsMuted);
  const queueTracks = useSelector(selectQueueTracks);
  const currentQueueIndex = useSelector(selectCurrentIndex);

  // Store pre-mute volume so unmute restores the user's prior level.
  const preMuteVolumeRef = useRef<number>(0.5);

  const {
    playEnhanced,
    playNormal,
    seekTo,
    pausePlayback,
    resumePlayback,
    stopPlayback,
    setVolume: setStreamingVolume,
    isStreaming,
    streamingState,
    processedChunks,
    totalChunks,
    currentTime,
    isPaused,
    isSeeking,
    error,
  } = usePlayEnhanced();

  // Every entry point reads the same live enhancement state. Disabled playback
  // uses the normal wire command; enabled playback preserves preset/intensity
  // instead of resetting to adaptive/1.0 (#4812/#4813).
  const {
    enabled: enhancementEnabled,
    preset: enhancementPreset,
    intensity: enhancementIntensity,
  } = useEnhancementControl();

  const startTrack = useCallback(
    (trackId: number) => enhancementEnabled
      ? playEnhanced(trackId, enhancementPreset, enhancementIntensity)
      : playNormal(trackId),
    [enhancementEnabled, enhancementPreset, enhancementIntensity, playEnhanced, playNormal]
  );

  const handleSeek = useCallback((position: number) => {
    if (!isStreaming && !currentTrack?.id) {
      DEBUG && console.warn('[PlaybackSession] Cannot seek: no track playing');
      return;
    }
    seekTo(position);
  }, [isStreaming, currentTrack?.id, seekTo]);

  const handleNext = useCallback(async () => {
    try {
      const nextIndex = currentQueueIndex + 1;
      if (nextIndex >= queueTracks.length) {
        DEBUG && console.log('[PlaybackSession] Already at last track in queue');
        return;
      }

      const nextTrackData = queueTracks[nextIndex];
      if (!nextTrackData) return;

      // Stop current playback, then sync queue index + player.currentTrack
      // atomically (#3587 — the previous nextTrack() + setCurrentTrack()
      // pair could observe an intermediate state between dispatches).
      stopPlayback();
      dispatch(setCurrentTrackAndSyncQueue(nextTrackData));

      await startTrack(nextTrackData.id);
    } catch (err) {
      console.error('[PlaybackSession] Next command error:', err);
    }
  }, [currentQueueIndex, queueTracks, stopPlayback, dispatch, startTrack]);

  const handlePrevious = useCallback(async () => {
    try {
      const prevIndex = currentQueueIndex - 1;
      if (prevIndex < 0) {
        DEBUG && console.log('[PlaybackSession] Already at first track in queue');
        return;
      }

      const prevTrackData = queueTracks[prevIndex];
      if (!prevTrackData) return;

      // Stop current playback, then sync queue index + player.currentTrack
      // atomically (#3587).
      stopPlayback();
      dispatch(setCurrentTrackAndSyncQueue(prevTrackData));

      await startTrack(prevTrackData.id);
    } catch (err) {
      console.error('[PlaybackSession] Previous command error:', err);
    }
  }, [currentQueueIndex, queueTracks, stopPlayback, dispatch, startTrack]);

  const handlePlayPause = useCallback(async () => {
    if (!currentTrack?.id) {
      DEBUG && console.warn('[PlaybackSession] No track loaded, cannot play');
      return;
    }

    try {
      // If already streaming, toggle pause/resume against the SAME session
      // instead of issuing a play_normal that would cancel it (#4541).
      if (isStreaming) {
        if (isPaused) {
          resumePlayback();
        } else {
          pausePlayback();
        }
      } else {
        await startTrack(currentTrack.id);
      }
    } catch (err) {
      console.error('[PlaybackSession] Play/Pause command error:', err);
    }
  }, [currentTrack?.id, isStreaming, isPaused, resumePlayback, pausePlayback, startTrack]);

  const handleVolumeChange = useCallback(async (vol: number) => {
    try {
      // Volume is 0-1 range in WebSocket/AudioEngine, 0-100 in Redux/Backend.
      setStreamingVolume(vol);
      dispatch(setVolumeAction(Math.round(vol * 100)));
    } catch (err) {
      console.error('[PlaybackSession] Volume command error:', err);
    }
  }, [setStreamingVolume, dispatch]);

  const handleMuteToggle = useCallback(async (): Promise<boolean> => {
    const volume = playerVolume ?? 50;
    const isMuted = volume === 0 || playerIsMuted === true;

    if (isMuted) {
      await handleVolumeChange(preMuteVolumeRef.current);
      return false;
    }
    preMuteVolumeRef.current = volume / 100;
    await handleVolumeChange(0);
    return true;
  }, [playerVolume, playerIsMuted, handleVolumeChange]);

  // Auto-advance to the next queue track once streaming completes near the
  // end of the current one. Lives here (not in Player.tsx) so it keeps
  // working regardless of which UI is mounted — the session is the source
  // of truth, not a side effect of one component's render tree.
  const hasAutoAdvancedRef = useRef(false);
  const trackDuration = currentTrack?.duration ?? 0;

  useEffect(() => {
    hasAutoAdvancedRef.current = false;
  }, [currentTrack?.id]);

  useEffect(() => {
    const isComplete = streamingState === 'complete';
    const nearEnd = trackDuration > 0 && currentTime >= trackDuration - 0.5;
    const hasMoreTracks = currentQueueIndex < queueTracks.length - 1;

    if (isComplete && nearEnd && hasMoreTracks && !hasAutoAdvancedRef.current) {
      hasAutoAdvancedRef.current = true;
      handleNext();
    }
  }, [streamingState, currentTime, trackDuration, currentQueueIndex, queueTracks.length, handleNext]);

  const value = useMemo<PlaybackSessionContextValue>(() => ({
    isStreaming,
    streamingState,
    processedChunks,
    totalChunks,
    currentTime,
    isPaused,
    isSeeking,
    error,
    startTrack,
    handleSeek,
    handlePlayPause,
    handleNext,
    handlePrevious,
    handleVolumeChange,
    handleMuteToggle,
  }), [
    isStreaming, streamingState, processedChunks, totalChunks,
    currentTime, isPaused, isSeeking, error, startTrack,
    handleSeek, handlePlayPause, handleNext, handlePrevious, handleVolumeChange, handleMuteToggle,
  ]);

  return (
    <PlaybackSessionContext.Provider value={value}>
      {children}
    </PlaybackSessionContext.Provider>
  );
}

export function usePlaybackSession(): PlaybackSessionContextValue {
  const ctx = useContext(PlaybackSessionContext);
  if (!ctx) {
    throw new Error('usePlaybackSession must be used within a PlaybackSessionProvider');
  }
  return ctx;
}
