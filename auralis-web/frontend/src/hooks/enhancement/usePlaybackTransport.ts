/**
 * Playback transport + position tracking for useAudioStreamingCore.
 *
 * stop/pause/resume/volume, plus the effects in playbackTransportEffects.ts
 * (engine gain, the 10 Hz current-time poll, the Redux isPlaying watch, the
 * resume-position getter registration and the disconnect keepalive), out of
 * useAudioStreamingCore.ts (#5478, #6703). This is the
 * "position tracking / transport" piece of the buffering/watchdog/position
 * split that issue asks for; buffering arithmetic lives in audioChunkIngest,
 * the watchdog in useStreamStartWatchdog.
 *
 * Effect/callback ORDER is behavior: the parent must call this hook exactly
 * where the moved sections used to sit (after the message handlers).
 *
 * @module hooks/enhancement/usePlaybackTransport
 */

import type { StreamCommand } from '@/types/ws/commands';
import { useCallback } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import type { AppDispatch } from '@/store';
import { endActiveStream } from '@/hooks/websocket/websocketConnectionState';
import type { useWebSocketContext } from '@/contexts/WebSocketContext';
import { resetStreaming, selectIsPlaying } from '@/store/slices/playerSlice';
import type { AudioPlaybackEngine } from '@/services/audio/AudioPlaybackEngine';
import type { StreamType } from './streamingCoreTypes';
import {
  useDisconnectKeepalive,
  useEnginePlayingSync,
  useEngineGainSync,
  usePlaybackClock,
  useResumePositionRegistration,
} from './playbackTransportEffects';

export interface PlaybackTransportDeps {
  wsContext: ReturnType<typeof useWebSocketContext>;

  streamType: StreamType;
  sendType: StreamCommand['type'];
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
    // Stop is client-side only (no WS stop), so end the tracked stream here or
    // a reconnect / enhancement toggle would start the track again (#5876).
    endActiveStream();
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

  // Effect ORDER is behavior: these run in the order they were declared
  // inline before #6703 (gain, clock, isPlaying sync, resume getter, keepalive).
  useEngineGainSync(playbackEngineRef);
  usePlaybackClock(isPlaying, playbackEngineRef, setCurrentTime);
  useEnginePlayingSync(isPlaying, isPaused, playbackEngineRef, resumePlayback, setIsPaused);
  useResumePositionRegistration(
    wsContext.setResumePositionGetter, sendType, acceptNormalStream, playbackEngineRef
  );
  useDisconnectKeepalive(wsContext.isConnected, playbackEngineRef, logPrefix, onDisconnectExtra);

  return { stopPlayback, pausePlayback, resumePlayback, setVolume };
}
