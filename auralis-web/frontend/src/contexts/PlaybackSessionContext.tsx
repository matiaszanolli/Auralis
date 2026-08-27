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
 * consume — split (#5006) into `usePlaybackControls()` (low-frequency) and
 * `usePlaybackProgress()` (the 10Hz position tick) in
 * `./playbackSessionContexts`, since a single combined context re-rendered
 * every consumer — including the app root — on every position update.
 *
 * @module contexts/PlaybackSessionContext
 */

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import type { AppDispatch } from '@/store';
import { usePlayEnhanced } from '@/hooks/enhancement/usePlayEnhanced';
import { useEnhancementControl } from '@/hooks/enhancement/useEnhancementControl';
import { selectQueueTracks, selectCurrentIndex } from '@/store/slices/queueSlice';
import { setVolume as setVolumeAction } from '@/store/slices/playerSlice';
import { setCurrentTrackAndSyncQueue } from '@/store/slices/playerQueueSync';
import { playerSelectors } from '@/store/selectors';
import {
  PlaybackControlsContext,
  PlaybackProgressContext,
  type PlaybackControlsContextValue,
  type PlaybackProgressContextValue,
} from './playbackSessionContexts';

const DEBUG = import.meta.env.DEV;

export function PlaybackSessionProvider({ children }: { children: ReactNode }) {
  const dispatch = useDispatch<AppDispatch>();

  const currentTrack = useSelector(playerSelectors.selectCurrentTrack);
  const playerVolume = useSelector(playerSelectors.selectVolume);
  const playerIsMuted = useSelector(playerSelectors.selectIsMuted);
  const queueTracks = useSelector(selectQueueTracks);
  const currentQueueIndex = useSelector(selectCurrentIndex);

  // Store pre-mute volume so unmute restores the user's prior level.
  const preMuteVolumeRef = useRef<number>(0.5);
  const commandPendingRef = useRef(false);
  const [isCommandPending, setIsCommandPending] = useState(false);

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

  const startTrackForSettings = useCallback(
    (trackId: number) => enhancementEnabled
      ? playEnhanced(trackId, enhancementPreset, enhancementIntensity)
      : playNormal(trackId),
    [enhancementEnabled, enhancementPreset, enhancementIntensity, playEnhanced, playNormal]
  );

  // The ref closes the gap before React can render disabled controls. This
  // coalesces double-clicks and keyboard repeats into the first command while
  // its playback request is still pending (#4835).
  const runTransportCommand = useCallback(async (command: () => void | Promise<void>) => {
    if (commandPendingRef.current) return;

    commandPendingRef.current = true;
    setIsCommandPending(true);
    try {
      await command();
    } finally {
      commandPendingRef.current = false;
      setIsCommandPending(false);
    }
  }, []);

  const startTrack = useCallback(
    (trackId: number) => runTransportCommand(() => startTrackForSettings(trackId)),
    [runTransportCommand, startTrackForSettings]
  );

  const handleSeek = useCallback((position: number) => {
    if (!isStreaming && !currentTrack?.id) {
      DEBUG && console.warn('[PlaybackSession] Cannot seek: no track playing');
      return;
    }
    seekTo(position);
  }, [isStreaming, currentTrack?.id, seekTo]);

  const handleNext = useCallback(() => runTransportCommand(async () => {
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

      await startTrackForSettings(nextTrackData.id);
    } catch (err) {
      console.error('[PlaybackSession] Next command error:', err);
    }
  }), [currentQueueIndex, queueTracks, stopPlayback, dispatch, runTransportCommand, startTrackForSettings]);

  const handlePrevious = useCallback(() => runTransportCommand(async () => {
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

      await startTrackForSettings(prevTrackData.id);
    } catch (err) {
      console.error('[PlaybackSession] Previous command error:', err);
    }
  }), [currentQueueIndex, queueTracks, stopPlayback, dispatch, runTransportCommand, startTrackForSettings]);

  const handlePlayPause = useCallback(() => runTransportCommand(async () => {
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
        await startTrackForSettings(currentTrack.id);
      }
    } catch (err) {
      console.error('[PlaybackSession] Play/Pause command error:', err);
    }
  }), [
    currentTrack?.id, isStreaming, isPaused, resumePlayback, pausePlayback,
    runTransportCommand, startTrackForSettings,
  ]);

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

  // #5006: split from one combined value into two, so a consumer that only
  // needs controls (ComfortableApp, usePlayTrack, usePlaylistContextActions)
  // does not re-render on the 10Hz currentTime tick that only Player/
  // ProgressBar actually need.
  const controlsValue = useMemo<PlaybackControlsContextValue>(() => ({
    isStreaming,
    streamingState,
    isPaused,
    isSeeking,
    isCommandPending,
    error,
    startTrack,
    handleSeek,
    handlePlayPause,
    handleNext,
    handlePrevious,
    handleVolumeChange,
    handleMuteToggle,
  }), [
    isStreaming, streamingState, isPaused, isSeeking, isCommandPending, error,
    startTrack, handleSeek, handlePlayPause, handleNext, handlePrevious,
    handleVolumeChange, handleMuteToggle,
  ]);

  const progressValue = useMemo<PlaybackProgressContextValue>(() => ({
    processedChunks,
    totalChunks,
    currentTime,
  }), [processedChunks, totalChunks, currentTime]);

  return (
    <PlaybackControlsContext.Provider value={controlsValue}>
      <PlaybackProgressContext.Provider value={progressValue}>
        {children}
      </PlaybackProgressContext.Provider>
    </PlaybackControlsContext.Provider>
  );
}

export { usePlaybackControls, usePlaybackProgress } from './playbackSessionContexts';
