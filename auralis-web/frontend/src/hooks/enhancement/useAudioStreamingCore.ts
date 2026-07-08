/**
 * useAudioStreamingCore Hook
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Shared WebSocket PCM streaming machinery for usePlayNormal and usePlayEnhanced
 * (fixes #4019 — the two hooks had drifted into ~500 lines of duplicated
 * buffer/flow-control/subscription logic with no shared implementation).
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
 * @module hooks/enhancement/useAudioStreamingCore
 */

const DEBUG = import.meta.env.DEV;

import { useCallback, useEffect, useRef, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import type { AppDispatch } from '@/store';
import type { useWebSocketContext } from '@/contexts/WebSocketContext';
import PCMStreamBuffer from '@/services/audio/PCMStreamBuffer';
import AudioPlaybackEngine from '@/services/audio/AudioPlaybackEngine';
import {
  updateStreamingProgress,
  completeStreaming,
  setStreamingError,
  resetStreaming,
  selectIsPlaying,
} from '@/store/slices/playerSlice';
import { decodeAudioChunkMessage } from '@/utils/audio/pcmDecoding';
import type {
  AudioStreamStartMessage,
  AudioChunkMessage,
  AudioStreamEndMessage,
  AudioStreamErrorMessage,
} from '@/contexts/WebSocketContext';

export interface StreamingMetadata {
  sampleRate: number;
  channels: number;
  totalChunks: number;
  processedChunks: number;
}

export type StreamType = 'normal' | 'enhanced';

export interface StreamingCoreOptions {
  /** Redux streaming slice this stream drives ('normal' | 'enhanced'). */
  streamType: StreamType;
  /** Key used for `wsContext.setResumePositionGetter` (e.g. 'play_normal'). */
  sendType: string;
  /** Console log prefix, e.g. '[usePlayNormal]'. */
  logPrefix: string;
  /** Buffered-sample threshold at which playback auto-starts. */
  getStartThreshold: (metadata: StreamingMetadata, engine: AudioPlaybackEngine) => number;
  /** Enhanced-only: dispatch progress at most every 10% instead of every chunk (#2535). */
  throttleProgress: boolean;
  /** Enhanced-only: detect and recover from out-of-order chunks after a missed stream_start. */
  detectOutOfSequence: boolean;
  /** Normal-only: close the AudioContext on every stop/error, not just unmount. */
  closeContextOnCleanup: boolean;
  /** Extra cleanup to run at the end of cleanupStreaming() (e.g. enhanced's isSeeking reset). */
  onCleanupExtra?: () => void;
  /** Extra work to run when the WebSocket disconnects (e.g. enhanced's fingerprint-timeout clear). */
  onDisconnectExtra?: () => void;
}

export interface StreamingCoreReturn {
  // Populated by the caller every render: `handleStreamStartRef.current = handleStreamStart`.
  handleStreamStartRef: React.MutableRefObject<(message: AudioStreamStartMessage) => void>;

  // Refs the caller's handleStreamStart/start-function populate directly.
  pcmBufferRef: React.MutableRefObject<PCMStreamBuffer | null>;
  playbackEngineRef: React.MutableRefObject<AudioPlaybackEngine | null>;
  audioContextRef: React.MutableRefObject<AudioContext | null>;
  abortRef: React.MutableRefObject<AbortController | undefined>;
  pendingChunksRef: React.MutableRefObject<AudioChunkMessage[]>;
  streamingMetadataRef: React.MutableRefObject<StreamingMetadata | null>;
  flowPausedRef: React.MutableRefObject<boolean>;
  lastReceivedChunkIndexRef: React.MutableRefObject<number>;
  lastDispatchedProgressRef: React.MutableRefObject<number>;

  currentTime: number;
  setCurrentTime: React.Dispatch<React.SetStateAction<number>>;
  isPaused: boolean;
  setIsPaused: React.Dispatch<React.SetStateAction<boolean>>;

  cleanupStreaming: () => void;
  handleChunk: (message: AudioChunkMessage) => void;
  handleStreamEnd: (message: AudioStreamEndMessage) => void;
  handleStreamError: (message: AudioStreamErrorMessage) => void;

  stopPlayback: () => void;
  pausePlayback: () => void;
  resumePlayback: () => void;
  setVolume: (volume: number) => void;
}

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
  const isPlaying = useSelector(selectIsPlaying);

  const pcmBufferRef = useRef<PCMStreamBuffer | null>(null);
  const playbackEngineRef = useRef<AudioPlaybackEngine | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const abortRef = useRef<AbortController>();
  const pendingChunksRef = useRef<AudioChunkMessage[]>([]);
  const streamingMetadataRef = useRef<StreamingMetadata | null>(null);
  const flowPausedRef = useRef<boolean>(false);
  const lastReceivedChunkIndexRef = useRef<number>(-1);
  const lastDispatchedProgressRef = useRef<number>(-1);

  const [currentTime, setCurrentTime] = useState(0);
  const [isPaused, setIsPaused] = useState(false);

  const cleanupStreaming = useCallback(() => {
    abortRef.current?.abort();

    pcmBufferRef.current?.dispose();
    pcmBufferRef.current = null;
    playbackEngineRef.current = null;
    streamingMetadataRef.current = null;
    pendingChunksRef.current = [];
    lastReceivedChunkIndexRef.current = -1;

    if (closeContextOnCleanup) {
      audioContextRef.current?.close();
      audioContextRef.current = null;
    }

    onCleanupExtra?.();
  }, [closeContextOnCleanup, onCleanupExtra]);

  const handleChunk = useCallback((message: AudioChunkMessage) => {
    try {
      // Only process messages intended for this stream (#2104)
      if (message.data.stream_type && message.data.stream_type !== streamType) return;

      const incomingChunkIndex = message.data?.chunk_index ?? 0;

      // If stream not yet initialized, queue the chunk instead of dropping it
      if (!pcmBufferRef.current || !streamingMetadataRef.current) {
        DEBUG && console.log(`${logPrefix} Queuing chunk until stream initialized:`, {
          chunkIndex: incomingChunkIndex,
          queueLength: pendingChunksRef.current.length + 1,
        });
        pendingChunksRef.current.push(message);
        return;
      }

      if (detectOutOfSequence) {
        // Detect out-of-sequence chunks indicating a new stream started without
        // a proper audio_stream_start (e.g. missed during WebSocket reconnect).
        const lastChunk = lastReceivedChunkIndexRef.current;
        if (lastChunk >= 0 && incomingChunkIndex < lastChunk - 1) {
          DEBUG && console.warn(`${logPrefix} Out-of-sequence chunk detected:`, {
            expected: lastChunk + 1,
            received: incomingChunkIndex,
            message: 'New stream may have started without audio_stream_start. This can cause audio discontinuity.',
          });
          // Reset the buffer to prevent audio glitches from stale data
          pcmBufferRef.current.reset();
          setCurrentTime(0);
          lastReceivedChunkIndexRef.current = -1;
        }
        lastReceivedChunkIndexRef.current = incomingChunkIndex;
      }

      // Decode PCM samples from base64
      const { samples, metadata } = decodeAudioChunkMessage(
        message,
        streamingMetadataRef.current.sampleRate,
        streamingMetadataRef.current.channels
      );

      // Append to circular buffer
      pcmBufferRef.current.append(samples, metadata.crossfadeSamples);

      // Flow control: tell backend to pause/resume sending based on buffer fill level.
      // 75% full → pause, 50% full → resume (25% hysteresis prevents rapid toggling).
      const fillPct = pcmBufferRef.current.getFillPercentage();
      if (fillPct > 75 && !flowPausedRef.current) {
        flowPausedRef.current = true;
        wsContext.send({ type: 'buffer_full', data: {} });
      } else if (fillPct < 50 && flowPausedRef.current) {
        flowPausedRef.current = false;
        wsContext.send({ type: 'buffer_ready', data: {} });
      }

      // Update tracking
      streamingMetadataRef.current.processedChunks++;
      const bufferedSamples = pcmBufferRef.current.getAvailableSamples();
      const progress =
        (streamingMetadataRef.current.processedChunks / streamingMetadataRef.current.totalChunks) * 100;
      const clampedProgress = Math.min(progress, 100);

      if (throttleProgress) {
        // Throttle Redux dispatches: only update at first chunk, every 10%
        // increment, or on completion — avoids O(n_chunks) Redux churn (#2535).
        const lastProgress = lastDispatchedProgressRef.current;
        const crossedDecile =
          Math.floor(clampedProgress / 10) > Math.floor(Math.max(0, lastProgress) / 10);
        if (lastProgress < 0 || crossedDecile || clampedProgress >= 100) {
          lastDispatchedProgressRef.current = clampedProgress;
          dispatch(
            updateStreamingProgress({
              streamType,
              processedChunks: streamingMetadataRef.current.processedChunks,
              bufferedSamples,
              progress: clampedProgress,
            })
          );
        }
      } else {
        dispatch(
          updateStreamingProgress({
            streamType,
            processedChunks: streamingMetadataRef.current.processedChunks,
            bufferedSamples,
            progress: clampedProgress,
          })
        );
      }

      // Auto-start playback once the caller's threshold is satisfied.
      const engine = playbackEngineRef.current;
      if (engine && !engine.isPlaying() && bufferedSamples >= getStartThreshold(streamingMetadataRef.current, engine)) {
        engine.startPlayback();
        setIsPaused(false);
      }

      DEBUG && console.debug(`${logPrefix} Chunk received:`, {
        chunkIndex: metadata.chunkIndex,
        frames: `${metadata.frameIndex + 1}/${metadata.frameCount}`,
        samples: metadata.sampleCount,
        buffered: `${(bufferedSamples / streamingMetadataRef.current.sampleRate).toFixed(1)}s`,
      });
    } catch (error) {
      const errorMsg = `Failed to process audio chunk: ${error instanceof Error ? error.message : String(error)}`;
      console.error(logPrefix, errorMsg);
      dispatch(setStreamingError({ streamType, error: errorMsg }));
    }
  }, [dispatch, wsContext, streamType, logPrefix, throttleProgress, detectOutOfSequence, getStartThreshold]);

  const handleStreamEnd = useCallback((message: AudioStreamEndMessage) => {
    // Only process messages intended for this stream (#2104)
    if (message.data.stream_type && message.data.stream_type !== streamType) return;

    DEBUG && console.log(`${logPrefix} Stream ended:`, {
      trackId: message.data.track_id,
      totalSamples: message.data.total_samples,
      duration: message.data.duration,
    });

    dispatch(completeStreaming(streamType));
  }, [dispatch, streamType, logPrefix]);

  const handleStreamError = useCallback((message: AudioStreamErrorMessage) => {
    // Only process messages intended for this stream (#2104)
    if (message.data.stream_type && message.data.stream_type !== streamType) return;

    const errorMsg = `Streaming error: ${message.data.error} (${message.data.code})`;
    console.error(logPrefix, errorMsg);
    dispatch(setStreamingError({ streamType, error: errorMsg }));
    cleanupStreaming();
  }, [dispatch, streamType, logPrefix, cleanupStreaming]);

  // #3588/#2532: ref indirection so handler identity changes don't force a
  // resubscribe — the only valid resubscribe trigger is wsContext changing
  // (i.e. a WS reconnect). handleStreamStartRef is populated by the caller
  // (`core.handleStreamStartRef.current = handleStreamStart`) since it's
  // defined hook-side, not by this core.
  const handleStreamStartRef = useRef<(message: AudioStreamStartMessage) => void>(() => {});
  const handleChunkRef = useRef(handleChunk);
  const handleStreamEndRef = useRef(handleStreamEnd);
  const handleStreamErrorRef = useRef(handleStreamError);
  handleChunkRef.current = handleChunk;
  handleStreamEndRef.current = handleStreamEnd;
  handleStreamErrorRef.current = handleStreamError;

  useEffect(() => {
    const unsubscribeStart = wsContext.subscribe(
      'audio_stream_start',
      (m) => handleStreamStartRef.current?.(m as AudioStreamStartMessage)
    );
    const unsubscribeChunk = wsContext.subscribe(
      'audio_chunk',
      (m) => handleChunkRef.current?.(m as AudioChunkMessage)
    );
    const unsubscribeEnd = wsContext.subscribe(
      'audio_stream_end',
      (m) => handleStreamEndRef.current?.(m as AudioStreamEndMessage)
    );
    const unsubscribeError = wsContext.subscribe(
      'audio_stream_error',
      (m) => handleStreamErrorRef.current?.(m as AudioStreamErrorMessage)
    );

    return () => {
      unsubscribeStart();
      unsubscribeChunk();
      unsubscribeEnd();
      unsubscribeError();
    };
  }, [wsContext]);

  const stopPlayback = useCallback(() => {
    playbackEngineRef.current?.stopPlayback();
    dispatch(resetStreaming(streamType));
    cleanupStreaming();
    setCurrentTime(0);
    setIsPaused(false);
  }, [dispatch, streamType, cleanupStreaming]);

  const pausePlayback = useCallback(() => {
    playbackEngineRef.current?.pausePlayback();
    setIsPaused(true);
  }, []);

  const resumePlayback = useCallback(() => {
    playbackEngineRef.current?.resumePlayback();
    setIsPaused(false);
  }, []);

  const setVolume = useCallback((volume: number) => {
    playbackEngineRef.current?.setVolume(Math.max(0, Math.min(1, volume)));
  }, []);

  // Update playback time periodically. Gated on isPlaying so the 10Hz
  // interval doesn't fire setCurrentTime gratuitously when idle (#3970).
  useEffect(() => {
    if (!isPlaying) return;

    const interval = setInterval(() => {
      const time = playbackEngineRef.current?.getCurrentPlaybackTime() || 0;
      setCurrentTime((prev) => (time === prev ? prev : time));
    }, 100);

    return () => clearInterval(interval);
  }, [isPlaying]);

  // Watch Redux isPlaying state and control AudioPlaybackEngine accordingly,
  // so usePlaybackControl.pause()/stop() stops the engine immediately without
  // waiting for buffered audio to drain (#2252).
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
        playbackEngineRef.current.resumePlayback();
        setIsPaused(false);
      }
    } else {
      playbackEngineRef.current.pausePlayback();
      setIsPaused(true);
    }
  }, [isPlaying]);

  // Register resume position getter for WS reconnect (#3185)
  useEffect(() => {
    wsContext.setResumePositionGetter(sendType, () =>
      playbackEngineRef.current?.getCurrentPlaybackTime() ?? 0
    );
    return () => wsContext.setResumePositionGetter(sendType, null);
  }, [wsContext, sendType]);

  // On WS disconnect: preserve playback engine and buffer so buffered audio
  // continues playing while reconnect happens (#3185, replaces #2847 teardown).
  useEffect(() => {
    if (!wsContext.isConnected && playbackEngineRef.current) {
      DEBUG && console.log(`${logPrefix} WebSocket disconnected - keeping playback engine alive`);
      onDisconnectExtra?.();
      // DO NOT destroy engine/buffer/state — let buffered audio play through.
    }
  }, [wsContext.isConnected, logPrefix, onDisconnectExtra]);

  return {
    handleStreamStartRef,
    pcmBufferRef,
    playbackEngineRef,
    audioContextRef,
    abortRef,
    pendingChunksRef,
    streamingMetadataRef,
    flowPausedRef,
    lastReceivedChunkIndexRef,
    lastDispatchedProgressRef,
    currentTime,
    setCurrentTime,
    isPaused,
    setIsPaused,
    cleanupStreaming,
    handleChunk,
    handleStreamEnd,
    handleStreamError,
    stopPlayback,
    pausePlayback,
    resumePlayback,
    setVolume,
  };
}

export default useAudioStreamingCore;
