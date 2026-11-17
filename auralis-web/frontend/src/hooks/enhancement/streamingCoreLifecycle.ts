/**
 * The teardown and auto-start halves of useAudioStreamingCore (#6275).
 *
 * Both are called at the same position in the core the inlined code used to occupy: hook and
 * effect order on the playback path is behaviour, so they stay contiguous blocks rather than
 * being reshuffled.
 */

import { useCallback, useEffect, useRef } from 'react';
import type { MutableRefObject } from 'react';
import { useDispatch } from 'react-redux';
import type { AppDispatch } from '@/store';
import type PCMStreamBuffer from '@/services/audio/PCMStreamBuffer';
import type AudioPlaybackEngine from '@/services/audio/AudioPlaybackEngine';
import type { AudioChunkMessage } from '@/contexts/WebSocketContext';
import { setStreamingError } from '@/store/slices/playerSlice';
import { STREAM_START_WATCHDOG_MS, useStreamStartWatchdog } from './useStreamStartWatchdog';
import type { StreamingCoreOptions, StreamingMetadata } from './streamingCoreTypes';

/** The refs cleanupStreaming resets. */
export interface StreamingTeardownRefs {
  abortRef: MutableRefObject<AbortController | undefined>;
  pcmBufferRef: MutableRefObject<PCMStreamBuffer | null>;
  playbackEngineRef: MutableRefObject<AudioPlaybackEngine | null>;
  audioContextRef: MutableRefObject<AudioContext | null>;
  streamingMetadataRef: MutableRefObject<StreamingMetadata | null>;
  pendingChunksRef: MutableRefObject<AudioChunkMessage[]>;
  lastReceivedChunkIndexRef: MutableRefObject<number>;
  streamEpochRef: MutableRefObject<number | null>;
  bufferEpochRef: MutableRefObject<number | null>;
}

/**
 * Watchdog for the first stream message after a play command (#4433) plus the teardown it and
 * every stop path share.
 *
 * The watchdog's timeout handler reaches cleanupStreaming through a ref rather than closing over
 * it: cleanupStreaming itself calls `clear`, so a direct dependency would be circular and neither
 * could be memoized (#5041).
 */
export function useStreamingTeardown(
  refs: StreamingTeardownRefs,
  { streamType, logPrefix, closeContextOnCleanup, onCleanupExtra }: Pick<
    StreamingCoreOptions,
    'streamType' | 'logPrefix' | 'closeContextOnCleanup' | 'onCleanupExtra'
  >
) {
  const dispatch = useDispatch<AppDispatch>();
  const {
    abortRef, pcmBufferRef, playbackEngineRef, audioContextRef, streamingMetadataRef,
    pendingChunksRef, lastReceivedChunkIndexRef, streamEpochRef, bufferEpochRef,
  } = refs;

  const cleanupStreamingRef = useRef<() => void>(() => {});
  const { arm: armStreamStartWatchdog, clear: clearStreamStartWatchdog } =
    useStreamStartWatchdog(() => {
      console.error(
        `${logPrefix} No audio stream started within ${STREAM_START_WATCHDOG_MS}ms — surfacing error`
      );
      dispatch(
        setStreamingError({
          streamType,
          error: 'Timed out waiting for the audio stream to start. Please try again.',
        })
      );
      cleanupStreamingRef.current();
    });

  const cleanupStreaming = useCallback(() => {
    clearStreamStartWatchdog();
    abortRef.current?.abort();

    pcmBufferRef.current?.dispose();
    pcmBufferRef.current = null;
    playbackEngineRef.current?.dispose();
    playbackEngineRef.current = null;
    streamingMetadataRef.current = null;
    pendingChunksRef.current = [];
    lastReceivedChunkIndexRef.current = -1;
    streamEpochRef.current = null;
    bufferEpochRef.current = null;

    if (closeContextOnCleanup) {
      audioContextRef.current?.close();
      audioContextRef.current = null;
    }

    onCleanupExtra?.();
  }, [
    closeContextOnCleanup, onCleanupExtra, clearStreamStartWatchdog, abortRef, pcmBufferRef,
    playbackEngineRef, audioContextRef, streamingMetadataRef, pendingChunksRef,
    lastReceivedChunkIndexRef, streamEpochRef, bufferEpochRef,
  ]);

  useEffect(() => {
    cleanupStreamingRef.current = cleanupStreaming;
  }, [cleanupStreaming]);

  return { armStreamStartWatchdog, clearStreamStartWatchdog, cleanupStreaming };
}

interface AutoStartDeps {
  pcmBufferRef: MutableRefObject<PCMStreamBuffer | null>;
  playbackEngineRef: MutableRefObject<AudioPlaybackEngine | null>;
  streamingMetadataRef: MutableRefObject<StreamingMetadata | null>;
  getStartThreshold: StreamingCoreOptions['getStartThreshold'];
  setIsPaused: (paused: boolean) => void;
}

/**
 * #5459: `pauseHoldRef` is set by a user pause and kept across a seek, a WS reconnect-resume or
 * an error auto-resume, so a stream that buffers while paused stays paused. Pause is client-side
 * only - the backend keeps streaming - and a seek stops the engine outright, so without this the
 * next buffered chunk started playback on its own. Cleared by resume, stop and a new play
 * command. The Redux isPlaying effect does NOT set it: backend player_state broadcasts write
 * that flag, and a stray `false` must not wedge the next track.
 *
 * `startPlaybackWhenBuffered` is the one auto-start rule: every path that might begin playback -
 * a chunk landing, the stream-start drain, a resume - goes through it.
 */
export function useAutoStartWhenBuffered({
  pcmBufferRef, playbackEngineRef, streamingMetadataRef, getStartThreshold, setIsPaused,
}: AutoStartDeps) {
  const pauseHoldRef = useRef(false);
  const getStartThresholdRef = useRef(getStartThreshold);
  getStartThresholdRef.current = getStartThreshold;

  const startPlaybackWhenBuffered = useCallback(() => {
    const engine = playbackEngineRef.current;
    const buffer = pcmBufferRef.current;
    const metadata = streamingMetadataRef.current;
    if (!engine || !buffer || !metadata || pauseHoldRef.current || engine.isPlaying()) return;
    const available = buffer.getAvailableSamples();
    // A stream that has ended will not grow: start with whatever it delivered (#5900).
    const shortStream = engine.hasStreamEnded() && available > 0;
    if (shortStream || available >= getStartThresholdRef.current(metadata, engine)) {
      engine.startPlayback();
      setIsPaused(false);
    }
  }, [playbackEngineRef, pcmBufferRef, streamingMetadataRef, setIsPaused]);

  return { pauseHoldRef, startPlaybackWhenBuffered };
}
