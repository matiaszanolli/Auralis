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
import { selectQueueTracks, selectCurrentIndex, selectRepeatMode } from '@/store/slices/queueSlice';
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
  const repeatMode = useSelector(selectRepeatMode);

  // Store pre-mute volume so unmute restores the user's prior level.
  const preMuteVolumeRef = useRef<number>(0.5);
  const commandPendingRef = useRef(false);
  const pendingCommandRef = useRef<Promise<void> | null>(null);
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

  // The ref closes the gap before React can render disabled controls. This
  // coalesces double-clicks and keyboard repeats into the first command while
  // its playback request is still pending (#4835). Returns whether the command
  // started (false = dropped because another is pending) — user-initiated
  // track selection must react to a drop, transport next/previous treat
  // coalescing as the desired behaviour (#5613).
  const runTransportCommand = useCallback(async (command: () => void | Promise<void>): Promise<boolean> => {
    if (commandPendingRef.current) return false;

    commandPendingRef.current = true;
    setIsCommandPending(true);
    const execution = (async () => {
      try {
        await command();
      } finally {
        commandPendingRef.current = false;
        setIsCommandPending(false);
      }
    })();
    pendingCommandRef.current = execution;
    try {
      await execution;
    } finally {
      if (pendingCommandRef.current === execution) pendingCommandRef.current = null;
    }
    return true;
  }, []);

  const startTrack = useCallback(
    async (trackId: number) => {
      const started = await runTransportCommand(() => startTrackForSettings(trackId));
      if (started) return;

      // #5613: by the time startTrack runs, the queue POST for this track has
      // already succeeded — silently dropping the start left the backend queue
      // on this track while the previous one kept playing. Wait out the
      // in-flight command and retry once.
      await pendingCommandRef.current;
      await runTransportCommand(() => startTrackForSettings(trackId));
    },
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
      let nextIndex = currentQueueIndex + 1;
      if (nextIndex >= queueTracks.length) {
        // Manual navigation follows the displayed order, so wrapping behaves
        // identically under shuffle — the queue slice already holds the
        // shuffled sequence. repeat 'one' is a track-END mode, not a
        // navigation mode: Next still advances off the last track (#5605).
        if (repeatMode !== 'all' || queueTracks.length === 0) {
          DEBUG && console.log('[PlaybackSession] Already at last track in queue');
          return;
        }
        nextIndex = 0;
      }

      const nextTrackData = queueTracks[nextIndex];
      if (!nextTrackData) return;

      // Stop current playback, then sync queue index + player.currentTrack
      // atomically (#3587 — the previous nextTrack() + setCurrentTrack()
      // pair could observe an intermediate state between dispatches).
      stopPlayback();
      dispatch(setCurrentTrackAndSyncQueue(nextTrackData, nextIndex));

      await startTrackForSettings(nextTrackData.id);
    } catch (err) {
      console.error('[PlaybackSession] Next command error:', err);
    }
  }), [currentQueueIndex, queueTracks, repeatMode, stopPlayback, dispatch, runTransportCommand, startTrackForSettings]);

  const handlePrevious = useCallback(() => runTransportCommand(async () => {
    try {
      let prevIndex = currentQueueIndex - 1;
      if (prevIndex < 0) {
        // Wrap to the last track under repeat 'all' (#5605); otherwise clamp.
        if (repeatMode !== 'all' || queueTracks.length === 0) {
          DEBUG && console.log('[PlaybackSession] Already at first track in queue');
          return;
        }
        prevIndex = queueTracks.length - 1;
      }

      const prevTrackData = queueTracks[prevIndex];
      if (!prevTrackData) return;

      // Stop current playback, then sync queue index + player.currentTrack
      // atomically (#3587).
      stopPlayback();
      dispatch(setCurrentTrackAndSyncQueue(prevTrackData, prevIndex));

      await startTrackForSettings(prevTrackData.id);
    } catch (err) {
      console.error('[PlaybackSession] Previous command error:', err);
    }
  }), [currentQueueIndex, queueTracks, repeatMode, stopPlayback, dispatch, runTransportCommand, startTrackForSettings]);

  const handlePlayPause = useCallback(() => runTransportCommand(async () => {
    if (!currentTrack?.id) {
      DEBUG && console.warn('[PlaybackSession] No track loaded, cannot play');
      return;
    }

    try {
      // If a session is already active, toggle pause/resume against the SAME
      // session instead of issuing a play_normal that would cancel it (#4541).
      if (isPlaybackActive) {
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
    currentTrack?.id, isPlaybackActive, isPaused, resumePlayback, pausePlayback,
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

  // Reset the auto-advance latch when a new track starts OR playback leaves
  // the completed state — the repeat-'one' restart (#5605) re-plays the same
  // id, so the id-change reset alone would leave the latch stuck set.
  // Resetting only while NOT complete preserves the one-trigger-per-completion
  // guard: during a single completion window the state stays 'complete'.
  useEffect(() => {
    if (streamingState !== 'complete') {
      hasAutoAdvancedRef.current = false;
    }
  }, [currentTrack?.id, streamingState]);

  useEffect(() => {
    const isComplete = streamingState === 'complete';
    const nearEnd = trackDuration > 0 && currentTime >= trackDuration - 0.5;
    if (!isComplete || !nearEnd || hasAutoAdvancedRef.current) return;

    // #5605: repeat 'one' restarts the current track at its beginning;
    // otherwise advance, wrapping to index 0 under repeat 'all' (handleNext
    // owns the wrap). repeat 'off' keeps the old behaviour: the queue ends.
    if (repeatMode === 'one') {
      if (currentTrack?.id == null) return;
      hasAutoAdvancedRef.current = true;
      startTrack(currentTrack.id);
      return;
    }

    const hasMoreTracks = currentQueueIndex < queueTracks.length - 1;
    if (hasMoreTracks || (repeatMode === 'all' && queueTracks.length > 0)) {
      hasAutoAdvancedRef.current = true;
      handleNext();
    }
  }, [streamingState, currentTime, trackDuration, currentQueueIndex, queueTracks.length, repeatMode, currentTrack?.id, startTrack, handleNext]);

  // #5006: split from one combined value into two, so a consumer that only
  // needs controls (ComfortableApp, usePlayTrack, usePlaylistContextActions)
  // does not re-render on the 10Hz currentTime tick that only Player/
  // ProgressBar actually need.
  const controlsValue = useMemo<PlaybackControlsContextValue>(() => ({
    isStreaming,
    isPlaybackActive,
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
    isStreaming, isPlaybackActive, streamingState, isPaused, isSeeking, isCommandPending, error,
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
