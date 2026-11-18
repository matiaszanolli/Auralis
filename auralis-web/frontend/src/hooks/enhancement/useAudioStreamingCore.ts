/**
 * useAudioStreamingCore Hook
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Shared WebSocket PCM streaming machinery, factored out when the normal
 * and enhanced playback hooks had drifted into ~500 lines of duplicated
 * buffer/flow-control/subscription logic (fixes #4019). usePlayEnhanced is
 * the sole consumer; there is no normal-playback hook anymore (#4541).
 *
 * Owns: PCM buffer/engine/context refs, the buffer-fill flow-control handshake,
 * chunk decoding + append, stream-end/error handling, playback transport
 * (stop/pause/resume/volume), current-time polling, and the Redux-isPlaying
 * watch effect. Per-hook behavioral differences (out-of-sequence chunk
 * detection, progress-dispatch throttling, playback start threshold, and
 * whether the AudioContext is closed outside of unmount) are passed in via
 * `StreamingCoreOptions` so both hooks keep their exact prior behavior.
 *
 * `handleStreamStart` and the public start/seek functions stay hook-local —
 * they differ too much (seek offset, fingerprint reset, preset/intensity) to
 * share safely.
 *
 * The concern modules this hook composes (#5041, #5478): the pure chunk
 * arithmetic in ./audioChunkIngest, the watchdog in ./useStreamStartWatchdog,
 * the message handlers + subscription wiring in ./useStreamMessageHandlers,
 * the transport/position effects in ./usePlaybackTransport, and the shared
 * types in ./streamingCoreTypes. This file owns the refs and the composition;
 * sub-hooks must be called in the order the sections originally appeared —
 * effect order is behavior.
 *
 * @module hooks/enhancement/useAudioStreamingCore
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useDispatch } from 'react-redux';
import type { AppDispatch } from '@/store';
import type { useWebSocketContext } from '@/contexts/WebSocketContext';
import PCMStreamBuffer from '@/services/audio/PCMStreamBuffer';
import AudioPlaybackEngine from '@/services/audio/AudioPlaybackEngine';
import { useStreamMessageHandlers } from './useStreamMessageHandlers';
import { startFlowDrainWatch } from './flowDrainWatch';
import { useStreamSubscriptions } from './useStreamSubscriptions';
import { usePlaybackTransport } from './usePlaybackTransport';
import { useAutoStartWhenBuffered, useStreamingTeardown } from './streamingCoreLifecycle';
import type {
  AudioStreamStartMessage,
  AudioChunkMessage,
} from '@/contexts/WebSocketContext';
import type {
  StreamingCoreOptions,
  StreamingCoreReturn,
  StreamingMetadata,
  StreamType,
} from './streamingCoreTypes';

// Re-exported, not redefined: the timer itself now lives in
// useStreamStartWatchdog (#5041), but tests import the constant from here.
export { STREAM_START_WATCHDOG_MS } from './useStreamStartWatchdog';

// Re-exported for the existing importers of this module; the definitions
// live in ./streamingCoreTypes (#5478).
export type {
  StreamingMetadata,
  StreamType,
  StreamingCoreOptions,
  StreamingCoreReturn,
} from './streamingCoreTypes';

/**
 * Shared PCM streaming core. See module docstring for what's shared vs.
 * kept hook-local.
 *
 * `handleStreamStart` is supplied via a ref the caller populates each render
 * (`core.handleStreamStartRef.current = handleStreamStart`) rather than as a
 * constructor argument — handleStreamStart's body needs this hook's refs, so
 * a constructor argument would create a forward reference across the two
 * hooks. This also matches the ref-indirection pattern already used
 * throughout this module.
 */
export function useAudioStreamingCore(
  wsContext: ReturnType<typeof useWebSocketContext>,
  options: StreamingCoreOptions
): StreamingCoreReturn {
  const {
    streamType,
    acceptNormalStream = false,
    sendType,
    logPrefix,
    getStartThreshold,
    throttleProgress,
    detectOutOfSequence,
    closeContextOnCleanup,
    onCleanupExtra,
    onDisconnectExtra,
  } = options;

  const dispatch = useDispatch<AppDispatch>();

  const pcmBufferRef = useRef<PCMStreamBuffer | null>(null);
  const playbackEngineRef = useRef<AudioPlaybackEngine | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const abortRef = useRef<AbortController>();
  const pendingChunksRef = useRef<AudioChunkMessage[]>([]);
  const streamingMetadataRef = useRef<StreamingMetadata | null>(null);
  const flowPausedRef = useRef<boolean>(false);
  const lastReceivedChunkIndexRef = useRef<number>(-1);
  /** Epoch of the stream the current audio_stream_start opened (#4563). */
  const streamEpochRef = useRef<number | null>(null);
  /** Epoch the ring's current content belongs to (#5861). */
  const bufferEpochRef = useRef<number | null>(null);
  const lastDispatchedProgressRef = useRef<number>(-1);
  /** Bounds handleStreamError's auto-resume to one attempt per distinct
   *  (trackId, recovery_position) pair, so a chunk that keeps failing at the
   *  same recovery point can't loop the stream forever (#4655). */
  const lastRecoveryAttemptRef = useRef<{ trackId: number; position: number } | null>(null);

  const [currentTime, setCurrentTime] = useState(0);
  const [isPaused, setIsPaused] = useState(false);

  // #3588/#2532: ref indirection so handler identity changes don't force a
  // resubscribe — the only valid resubscribe trigger is `subscribe` changing (#6426).
  // handleStreamStartRef is populated by the caller (`core.handleStreamStartRef.current =
  // handleStreamStart`) since it's defined hook-side, not by this core.
  const handleStreamStartRef = useRef<(message: AudioStreamStartMessage) => void>(() => {});

  const acceptsStreamType = useCallback(
    (incoming: StreamType | undefined) =>
      incoming === undefined ||
      incoming === streamType ||
      (acceptNormalStream && incoming === 'normal'),
    [acceptNormalStream, streamType]
  );

  const { armStreamStartWatchdog, clearStreamStartWatchdog, cleanupStreaming } = useStreamingTeardown(
    {
      abortRef, pcmBufferRef, playbackEngineRef, audioContextRef, streamingMetadataRef,
      pendingChunksRef, lastReceivedChunkIndexRef, streamEpochRef, bufferEpochRef,
    },
    { streamType, logPrefix, closeContextOnCleanup, onCleanupExtra }
  );

  const { pauseHoldRef, startPlaybackWhenBuffered } = useAutoStartWhenBuffered({
    pcmBufferRef, playbackEngineRef, streamingMetadataRef, getStartThreshold, setIsPaused,
  });

  // #5863: the resume half of flow control cannot wait for the next chunk
  // (the server parks on its flow gate after buffer_full and sends nothing).
  // The drain watch polls the fill level from the playback side and emits
  // buffer_ready when it drops below the resume threshold.
  const { send } = wsContext; // identity-stable; the context object is not (#6426)
  useEffect(() => {
    return startFlowDrainWatch({
      flowPausedRef,
      pcmBufferRef,
      send,
    });
  }, [flowPausedRef, pcmBufferRef, send]);

  // Chunk/end/error handling + the four stream-message subscriptions. Called
  // exactly where these sections used to live — effect order is behavior.
  const { handleChunk, handleStreamEnd, handleStreamError } = useStreamMessageHandlers({
    wsContext,
    dispatch,
    streamType,
    logPrefix,
    throttleProgress,
    detectOutOfSequence,
    pcmBufferRef,
    playbackEngineRef,
    pendingChunksRef,
    streamingMetadataRef,
    flowPausedRef,
    lastReceivedChunkIndexRef,
    lastDispatchedProgressRef,
    streamEpochRef,

    lastRecoveryAttemptRef,
    acceptsStreamType,
    startPlaybackWhenBuffered,
    cleanupStreaming,
    setCurrentTime,
  });

  useStreamSubscriptions({
    wsContext,
    logPrefix,
    streamEpochRef,
    bufferEpochRef,
    handleStreamStartRef,
    acceptsStreamType,
    clearStreamStartWatchdog,
    handleChunk,
    handleStreamEnd,
    handleStreamError,
  });

  // Transport (stop/pause/resume/volume), position polling, resume-getter
  // registration and the Redux isPlaying watch — same position as the
  // original sections.
  const {
    stopPlayback,
    pausePlayback,
    resumePlayback,
    setVolume,
  } = usePlaybackTransport({
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
  });

  return {
    handleStreamStartRef,
    bufferEpochRef,
    pcmBufferRef,
    playbackEngineRef,
    audioContextRef,
    abortRef,
    pendingChunksRef,
    streamingMetadataRef,
    flowPausedRef,
    lastReceivedChunkIndexRef,
    lastDispatchedProgressRef,
    pauseHoldRef,
    currentTime,
    setCurrentTime,
    isPaused,
    setIsPaused,
    cleanupStreaming,
    armStreamStartWatchdog,
    handleChunk,
    handleStreamEnd,
    handleStreamError,
    startPlaybackWhenBuffered,
    stopPlayback,
    pausePlayback,
    resumePlayback,
    setVolume,
  };
}

export default useAudioStreamingCore;
