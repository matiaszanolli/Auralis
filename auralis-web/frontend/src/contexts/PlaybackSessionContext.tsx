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

import { useCallback, useMemo, type ReactNode } from 'react';
import { useSelector } from 'react-redux';
import { usePlayEnhanced } from '@/hooks/enhancement/usePlayEnhanced';
import { useEnhancementControl } from '@/hooks/enhancement/useEnhancementControl';
import { selectQueueTracks, selectCurrentIndex, selectRepeatMode } from '@/store/slices/queueSlice';
import { playerSelectors } from '@/store/selectors';
import {
  PlaybackControlsContext,
  PlaybackProgressContext,
  type PlaybackControlsContextValue,
  type PlaybackProgressContextValue,
} from './playbackSessionContexts';
import { useAutoAdvance, useStartTrackRetry, useTransportCommand } from './usePlaybackSessionHooks';
import { useFollowRemovedTrack, useStopForClearedQueue } from './useFollowRemovedTrack';
import { usePlaybackNavigation } from './usePlaybackNavigation';
import { usePlaybackVolume } from './usePlaybackVolume';

const DEBUG = import.meta.env.DEV;

export function PlaybackSessionProvider({ children }: { children: ReactNode }) {
  const currentTrack = useSelector(playerSelectors.selectCurrentTrack);
  const playerVolume = useSelector(playerSelectors.selectVolume);
  const playerIsMuted = useSelector(playerSelectors.selectIsMuted);
  const queueTracks = useSelector(selectQueueTracks);
  const currentQueueIndex = useSelector(selectCurrentIndex);
  const repeatMode = useSelector(selectRepeatMode);

  const gate = useTransportCommand();
  const { runTransportCommand, isCommandPending } = gate;

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

  // Delivery ('complete') finishes well before playback ends, and the engine
  // keeps playing the buffered tail. Treat that tail as an active session so
  // play/pause toggles it instead of restarting the track (#5603). The boolean
  // only flips at the track end, so the controls value stays stable across the
  // 10Hz currentTime tick (#5006). An unknown duration cannot be judged, so it
  // keeps the previous behaviour (not active).
  const trackDuration = currentTrack?.duration ?? 0;
  const playbackEnded = trackDuration > 0 && currentTime >= trackDuration - 0.5;
  const isPlaybackActive =
    isStreaming || (streamingState === 'complete' && trackDuration > 0 && !playbackEnded);

  const startTrackForSettings = useCallback(
    (trackId: number) => enhancementEnabled
      ? playEnhanced(trackId, enhancementPreset, enhancementIntensity)
      : playNormal(trackId),
    [enhancementEnabled, enhancementPreset, enhancementIntensity, playEnhanced, playNormal]
  );

  const startTrack = useStartTrackRetry(gate, startTrackForSettings);
  const followRemovedTrack = useFollowRemovedTrack({
    gate, stopPlayback, startTrackForSettings, isRunning: isPlaybackActive && !isPaused,
  });
  const stopForClearedQueue = useStopForClearedQueue({ gate, stopPlayback, isPlaybackActive });

  const handleSeek = useCallback((position: number) => {
    if (!isStreaming && !currentTrack?.id) {
      DEBUG && console.warn('[PlaybackSession] Cannot seek: no track playing');
      return;
    }
    seekTo(position);
  }, [isStreaming, currentTrack?.id, seekTo]);

  const { advanceNext, handleNext, handlePrevious, startQueued } = usePlaybackNavigation({
    queueTracks, currentQueueIndex, repeatMode, runTransportCommand, stopPlayback, startTrackForSettings,
    hasCurrentTrack: currentTrack != null,
  });

  const handlePlayPause = useCallback(async () => {
    // A queue built while idle (#6591); an active session without a track still pauses (#6561).
    if (!currentTrack?.id && !isPlaybackActive) return startQueued();
    await runTransportCommand(async () => {

    try {
      // If a session is already active, toggle pause/resume against the SAME
      // session instead of issuing a play_normal that would cancel it (#4541).
      if (isPlaybackActive) {
        if (isPaused) {
          resumePlayback();
        } else {
          pausePlayback();
        }
      } else if (currentTrack?.id) {
        await startTrackForSettings(currentTrack.id);
      }
    } catch (err) {
      console.error('[PlaybackSession] Play/Pause command error:', err);
    }
    });
  }, [
    currentTrack, isPlaybackActive, isPaused, resumePlayback, pausePlayback,
    runTransportCommand, startTrackForSettings, startQueued,
  ]);

  const { handleVolumeChange, handleMuteToggle } = usePlaybackVolume({
    playerVolume, playerIsMuted, setStreamingVolume,
  });

  useAutoAdvance({
    streamingState,
    currentTime,
    trackDuration,
    repeatMode,
    currentTrackId: currentTrack?.id,
    currentQueueIndex,
    queueLength: queueTracks.length,
    startTrack,
    advanceNext,
    isCommandPending,
  });

  // #5006: two values, so controls-only consumers skip the 10Hz currentTime re-render.
  const controlsValue = useMemo<PlaybackControlsContextValue>(() => ({
    isStreaming,
    isPlaybackActive,
    streamingState,
    isPaused,
    isSeeking,
    isCommandPending,
    error,
    startTrack,
    followRemovedTrack,
    stopForClearedQueue,
    handleSeek,
    handlePlayPause,
    handleNext,
    handlePrevious,
    handleVolumeChange,
    handleMuteToggle,
  }), [
    isStreaming, isPlaybackActive, streamingState, isPaused, isSeeking, isCommandPending, error,
    startTrack, followRemovedTrack, stopForClearedQueue, handleSeek, handlePlayPause, handleNext, handlePrevious,
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
