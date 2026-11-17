/**
 * The audio_chunk handler of useStreamMessageHandlers: classify the frame, queue or drop it,
 * ingest it into the PCM ring, drive flow control and progress, and kick the auto-start rule.
 * Split out by lifecycle stage (#6275); the end/error stages stay in useStreamMessageHandlers.
 *
 * @module hooks/enhancement/useStreamChunkHandler
 */

const DEBUG = import.meta.env.DEV;

import { useCallback } from 'react';
import { updateStreamingProgress, setStreamingError } from '@/store/slices/playerSlice';
import {
  MAX_PENDING_CHUNK_FRAMES,
  classifyChunk,
  ingestChunk,
  isOutOfSequence,
  shouldDispatchProgress,
} from './audioChunkIngest';
import type { AudioChunkMessage } from '@/contexts/WebSocketContext';
import type { StreamMessageHandlerDeps } from './useStreamMessageHandlers';

export function useStreamChunkHandler({
  wsContext,
  dispatch,
  streamType,
  logPrefix,
  throttleProgress,
  detectOutOfSequence,
  pcmBufferRef,
  pendingChunksRef,
  flowPausedRef,
  streamingMetadataRef,
  lastReceivedChunkIndexRef,
  lastDispatchedProgressRef,
  streamEpochRef,
  acceptsStreamType,
  startPlaybackWhenBuffered,
  setCurrentTime,
}: StreamMessageHandlerDeps): (message: AudioChunkMessage) => void {
  return useCallback((message: AudioChunkMessage) => {
    try {
      const rejection = classifyChunk({
        message,
        currentEpoch: streamEpochRef.current,
        initialized: Boolean(pcmBufferRef.current && streamingMetadataRef.current),
        acceptsStreamType,
      });

      if (rejection === 'wrong-stream-type') return;

      if (rejection === 'superseded-epoch') {
        DEBUG && console.warn(`${logPrefix} Dropping chunk from superseded stream:`, {
          chunkEpoch: message.data.stream_epoch,
          currentEpoch: streamEpochRef.current,
          chunkIndex: message.data?.chunk_index,
        });
        return;
      }

      const incomingChunkIndex = message.data?.chunk_index ?? 0;

      if (rejection === 'not-initialized') {
        // Queue rather than drop — audio_stream_start may still be in flight —
        // but bounded: nothing drains the queue after a teardown (#5867).
        if (pendingChunksRef.current.length >= MAX_PENDING_CHUNK_FRAMES) {
          DEBUG && console.warn(`${logPrefix} Dropping chunk: no stream initialized and the queue is full`);
          return;
        }
        DEBUG && console.log(`${logPrefix} Queuing chunk until stream initialized:`, {
          chunkIndex: incomingChunkIndex,
          queueLength: pendingChunksRef.current.length + 1,
        });
        pendingChunksRef.current.push(message);
        return;
      }

      const buffer = pcmBufferRef.current!;
      const metadata = streamingMetadataRef.current!;

      if (detectOutOfSequence) {
        if (isOutOfSequence(lastReceivedChunkIndexRef.current, incomingChunkIndex)) {
          DEBUG && console.warn(`${logPrefix} Out-of-sequence chunk detected:`, {
            expected: lastReceivedChunkIndexRef.current + 1,
            received: incomingChunkIndex,
            message: 'New stream may have started without audio_stream_start. This can cause audio discontinuity.',
          });
          // Reset the buffer to prevent audio glitches from stale data
          buffer.reset();
          setCurrentTime(0);
          lastReceivedChunkIndexRef.current = -1;
        }
        lastReceivedChunkIndexRef.current = incomingChunkIndex;
      }

      const result = ingestChunk({
        message,
        buffer,
        metadata,
        flowPaused: flowPausedRef.current,
      });

      if (result.flowControl === 'pause') {
        flowPausedRef.current = true;
        wsContext.send({ type: 'buffer_full', data: {} });
      } else if (result.flowControl === 'resume') {
        flowPausedRef.current = false;
        wsContext.send({ type: 'buffer_ready', data: {} });
      }

      if (
        shouldDispatchProgress(
          result.clampedProgress,
          lastDispatchedProgressRef.current,
          throttleProgress
        )
      ) {
        if (throttleProgress) lastDispatchedProgressRef.current = result.clampedProgress;
        dispatch(
          updateStreamingProgress({
            streamType,
            processedChunks: metadata.processedChunks,
            bufferedSamples: result.bufferedSamples,
            progress: result.clampedProgress,
            trackId: message.data.track_id, // drop stale updates after a skip (#4434)
          })
        );
      }

      startPlaybackWhenBuffered();

      DEBUG && console.debug(`${logPrefix} Chunk received:`, {
        chunkIndex: result.chunkIndex,
        frames: `${result.frameIndex + 1}/${result.frameCount}`,
        samples: result.sampleCount,
        buffered: `${(result.bufferedSamples / metadata.sampleRate).toFixed(1)}s`,
      });
    } catch (error) {
      const errorMsg = `Failed to process audio chunk: ${error instanceof Error ? error.message : String(error)}`;
      console.error(logPrefix, errorMsg);
      dispatch(setStreamingError({ streamType, error: errorMsg }));
    }
    }, [
    dispatch, wsContext, streamType, logPrefix, throttleProgress, detectOutOfSequence,
    startPlaybackWhenBuffered, acceptsStreamType, setCurrentTime, pcmBufferRef, streamingMetadataRef,
    pendingChunksRef, flowPausedRef, lastReceivedChunkIndexRef, lastDispatchedProgressRef, streamEpochRef,
  ]);
}
