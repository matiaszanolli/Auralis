/**
 * Playback transport + position tracking for useAudioStreamingCore.
 *
 * stop/pause/resume/volume, the 10 Hz current-time poll, the resume-position
 * getter registration, the Redux isPlaying watch and the disconnect keepalive,
 * moved verbatim out of useAudioStreamingCore.ts (#5478). This is the
 * "position tracking / transport" piece of the buffering/watchdog/position
 * split that issue asks for; buffering arithmetic lives in audioChunkIngest,
 * the watchdog in useStreamStartWatchdog.
 *
 * Effect/callback ORDER is behavior: the parent must call this hook exactly
 * where the moved sections used to sit (after the message handlers).
 *
 * @module hooks/enhancement/usePlaybackTransport
 */

const DEBUG = import.meta.env.DEV;

import { useCallback, useEffect, useRef } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import type { AppDispatch } from '@/store';
import type { useWebSocketContext } from '@/contexts/WebSocketContext';
import {
  resetStreaming,
  selectIsPlaying,
  selectIsMuted,
  selectVolume,
  engineGainFromPlayerState,
} from '@/store/slices/playerSlice';
import type { AudioPlaybackEngine } from '@/services/audio/AudioPlaybackEngine';
import type { StreamType } from './streamingCoreTypes';

export interface PlaybackTransportDeps {
  wsContext: ReturnType<typeof useWebSocketContext>;

  streamType: StreamType;
  sendType: string;
  logPrefix: string;
  acceptNormalStream: boolean;
  onDisconnectExtra?: () => void;

  // Shared parent state/refs
  playbackEngineRef: React.MutableRefObject<AudioPlaybackEngine | null>;
  pauseHoldRef: React.MutableRefObject<boolean>;
  /** Set by a user pause; while set, buffered audio never starts on its own. */
  isPaused: boolean;
  setIsPaused: React.Dispatch<React.SetStateAction<boolean>>;
  setCurrentTime: React.Dispatch<React.SetStateAction<number>>;

  // Parent callbacks
  cleanupStreaming: () => void;
  /** The single auto-start rule (#5459) — resume goes through it too. */
  startPlaybackWhenBuffered: () => void;
}

export function usePlaybackTransport(deps: PlaybackTransportDeps) {
  const {
    wsContext,
    streamType,
    sendType,
    logPrefix,
    acceptNormalStream,
    onDisconnectExtra,
    playbackEngineRef,
    pauseHoldRef,
    isPaused,
    setIsPaused,
    setCurrentTime,
    cleanupStreaming,
    startPlaybackWhenBuffered,
  } = deps;

  const dispatch = useDispatch<AppDispatch>();
  const isPlaying = useSelector(selectIsPlaying);

  const stopPlayback = useCallback(() => {
    pauseHoldRef.current = false;
    playbackEngineRef.current?.stopPlayback();
    dispatch(resetStreaming(streamType));
    cleanupStreaming();
    setCurrentTime(0);
    setIsPaused(false);
  }, [dispatch, streamType, cleanupStreaming, pauseHoldRef, playbackEngineRef, setCurrentTime, setIsPaused]);

  const pausePlayback = useCallback(() => {
    pauseHoldRef.current = true;
    playbackEngineRef.current?.pausePlayback();
    setIsPaused(true);
  }, [pauseHoldRef, playbackEngineRef, setIsPaused]);

  const resumePlayback = useCallback(() => {
    pauseHoldRef.current = false;
    playbackEngineRef.current?.resumePlayback();
    setIsPaused(false);
    // resumePlayback() only restarts a *paused* engine. A seek made while paused
    // left it stopped with a refilled buffer, and flow control may have halted
    // delivery, so no further chunk would come along to start it (#5459).
    startPlaybackWhenBuffered();
  }, [pauseHoldRef, playbackEngineRef, setIsPaused, startPlaybackWhenBuffered]);

  const setVolume = useCallback((volume: number) => {
    playbackEngineRef.current?.setVolume(Math.max(0, Math.min(1, volume)));
  }, [playbackEngineRef]);

  // #5607: WS-sourced volume changes (volume_changed / player_state.volume)
  // and mute toggles reach only Redux — the imperative slider path above is
  // the only thing that touched the engine directly. Re-apply whenever the
  // authoritative gain changes so the current engine always matches the UI,
  // whatever the source. (Each NEW engine is seeded from the same
  // engineGainFromPlayerState conversion in useEnhancedStreamStart.)
  const playerVolume = useSelector(selectVolume);
  const playerIsMuted = useSelector(selectIsMuted);
  const engineGain = engineGainFromPlayerState({
    volume: playerVolume,
    isMuted: playerIsMuted,
  });
  useEffect(() => {
    playbackEngineRef.current?.setVolume(engineGain);
  }, [engineGain, playbackEngineRef]);

  // Update playback time periodically. Gated on isPlaying so the 10Hz
  // interval doesn't fire setCurrentTime gratuitously when idle (#3970).
  useEffect(() => {
    if (!isPlaying) return;

    const interval = setInterval(() => {
      const time = playbackEngineRef.current?.getCurrentPlaybackTime() || 0;
      setCurrentTime((prev) => (time === prev ? prev : time));
    }, 100);

    return () => clearInterval(interval);
  }, [isPlaying, playbackEngineRef, setCurrentTime]);

  // Watch Redux isPlaying state and control AudioPlaybackEngine accordingly,
  // so a pause/stop command stops the engine immediately without waiting for
  // buffered audio to drain (#2252).
  //
  // #3624: isPaused is read via a ref so it doesn't drive a re-run of this
  // effect; including it in deps caused two pausePlayback() calls per
  // transition because setIsPaused(true) re-fired the effect.
  const isPausedRef = useRef(isPaused);
  useEffect(() => {
    isPausedRef.current = isPaused;
  }, [isPaused]);

  useEffect(() => {
    if (!playbackEngineRef.current) return;

    if (isPlaying) {
      if (isPausedRef.current) {
        resumePlayback();
      }
    } else {
      playbackEngineRef.current.pausePlayback();
      setIsPaused(true);
    }
    // resumePlayback is stable (its only dependency is a []-memoized callback).
  }, [isPlaying, resumePlayback, playbackEngineRef, setIsPaused]);

  // Register resume position getter for WS reconnect (#3185).
  // Depends on setResumePositionGetter (stable, #3730), not the whole
  // wsContext object — the object's identity changes on every WS status
  // flicker, which used to unregister/re-register the getters for no reason
  // (#4668's missed sibling, #5621).
  useEffect(() => {
    const { setResumePositionGetter } = wsContext;
    const getPosition = () =>
      playbackEngineRef.current?.getCurrentPlaybackTime() ?? 0;
    setResumePositionGetter(sendType, getPosition);
    if (acceptNormalStream) {
      setResumePositionGetter('play_normal', getPosition);
    }
    return () => {
      setResumePositionGetter(sendType, null);
      if (acceptNormalStream) {
        setResumePositionGetter('play_normal', null);
      }
    };
  }, [wsContext.setResumePositionGetter, sendType, acceptNormalStream, playbackEngineRef]);

  // On WS disconnect: preserve playback engine and buffer so buffered audio
  // continues playing while reconnect happens (#3185, replaces #2847 teardown).
  useEffect(() => {
    if (!wsContext.isConnected && playbackEngineRef.current) {
      DEBUG && console.log(`${logPrefix} WebSocket disconnected - keeping playback engine alive`);
      onDisconnectExtra?.();
      // DO NOT destroy engine/buffer/state — let buffered audio play through.
    }
  }, [wsContext.isConnected, logPrefix, onDisconnectExtra, playbackEngineRef]);

  return { stopPlayback, pausePlayback, resumePlayback, setVolume };
}
