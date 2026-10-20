/**
 * Stream-message subscription wiring for useAudioStreamingCore.
 *
 * The single effect that subscribes audio_stream_start/chunk/end/error and
 * forwards them through handler refs, plus the epoch bookkeeping around
 * audio_stream_start (#4563/#5385) and the disconnect-epoch reset. Moved out
 * of useAudioStreamingCore.ts (#5478); the handlers themselves live in
 * ./useStreamMessageHandlers.
 *
 * Effect ORDER is behavior: the parent must call this hook exactly where the
 * subscription effect used to sit (after the handlers are built, before the
 * transport effects).
 *
 * @module hooks/enhancement/useStreamSubscriptions
 */

const DEBUG = import.meta.env.DEV;

import { useEffect, useRef } from 'react';
import type { useWebSocketContext } from '@/contexts/WebSocketContext';
import type {
  AudioStreamStartMessage,
  AudioChunkMessage,
  AudioStreamEndMessage,
  AudioStreamErrorMessage,
} from '@/contexts/WebSocketContext';
import type { StreamType } from './streamingCoreTypes';

export interface StreamSubscriptionDeps {
  wsContext: ReturnType<typeof useWebSocketContext>;

  streamType: StreamType;
  logPrefix: string;

  /** Epoch of the stream the current audio_stream_start opened (#4563). */
  streamEpochRef: React.MutableRefObject<number | null>;
  /** Populated by the caller of useAudioStreamingCore each render. */
  handleStreamStartRef: React.MutableRefObject<(message: AudioStreamStartMessage) => void>;

  // Parent callbacks
  acceptsStreamType: (incoming: StreamType | undefined) => boolean;
  clearStreamStartWatchdog: () => void;
  handleChunk: (message: AudioChunkMessage) => void;
  handleStreamEnd: (message: AudioStreamEndMessage) => void;
  handleStreamError: (message: AudioStreamErrorMessage) => void;
}

export function useStreamSubscriptions(deps: StreamSubscriptionDeps) {
  const {
    wsContext,
    streamType,
    logPrefix,
    streamEpochRef,
    handleStreamStartRef,
    acceptsStreamType,
    clearStreamStartWatchdog,
    handleChunk,
    handleStreamEnd,
    handleStreamError,
  } = deps;

  // #3588/#2532: ref indirection so handler identity changes don't force a
  // resubscribe — the only valid resubscribe trigger is wsContext changing
  // (i.e. a WS reconnect). handleStreamStartRef is populated by the caller
  // (`core.handleStreamStartRef.current = handleStreamStart`) since it's
  // defined hook-side, not by this core.
  const handleChunkRef = useRef(handleChunk);
  const handleStreamEndRef = useRef(handleStreamEnd);
  const handleStreamErrorRef = useRef(handleStreamError);
  handleChunkRef.current = handleChunk;
  handleStreamEndRef.current = handleStreamEnd;
  handleStreamErrorRef.current = handleStreamError;

  useEffect(() => {
    // Any incoming stream message means the backend is responding, so disarm
    // the first-stream watchdog (#4433).
    const unsubscribeStart = wsContext.subscribe(
      'audio_stream_start',
      (m) => {
        clearStreamStartWatchdog();
        const start = m as AudioStreamStartMessage;
        // Record the epoch here rather than in the callers' handleStreamStart
        // (#4563): this wrapper is the one choke point every stream type passes
        // through, so enhanced, normal, seek and reconnect-resume are all
        // covered without each having to remember. Must happen BEFORE the
        // caller's handler runs — that handler may synchronously flush queued
        // chunks through handleChunk, which reads this ref. Gate on stream_type
        // the same way the callers' handlers do, so a concurrently-mounted core
        // of the other type does not adopt this stream's epoch; dispatch itself
        // is left unfiltered, exactly as before.
        if (!acceptsStreamType(start.data?.stream_type)) return;
        // #5385: epochs only rise within a backend process, so a start carrying
        // a LOWER epoch than the adopted one is an older stream arriving late.
        // Adopting it would make the chunk filter reject the newer stream.
        // Unreachable while the backend serializes dispatch per connection;
        // this keeps it harmless if that ever changes. A backend restart
        // restarts the count, which is why the ref is forgotten on disconnect.
        const incomingEpoch = start.data?.stream_epoch;
        const currentEpoch = streamEpochRef.current;
        if (incomingEpoch != null && currentEpoch != null && incomingEpoch < currentEpoch) {
          DEBUG && console.warn(`${logPrefix} Ignoring audio_stream_start from a superseded stream:`, {
            startEpoch: incomingEpoch,
            currentEpoch,
          });
          return;
        }
        streamEpochRef.current = incomingEpoch ?? null;
        handleStreamStartRef.current?.(start);
      }
    );
    const unsubscribeChunk = wsContext.subscribe(
      'audio_chunk',
      (m) => { clearStreamStartWatchdog(); handleChunkRef.current?.(m as AudioChunkMessage); }
    );
    const unsubscribeEnd = wsContext.subscribe(
      'audio_stream_end',
      (m) => { clearStreamStartWatchdog(); handleStreamEndRef.current?.(m as AudioStreamEndMessage); }
    );
    const unsubscribeError = wsContext.subscribe(
      'audio_stream_error',
      (m) => { clearStreamStartWatchdog(); handleStreamErrorRef.current?.(m as AudioStreamErrorMessage); }
    );

    return () => {
      clearStreamStartWatchdog();
      unsubscribeStart();
      unsubscribeChunk();
      unsubscribeEnd();
      unsubscribeError();
    };
    // streamType is a per-instance constant, so listing it cannot cause the
    // resubscribe the comment above warns against.
  }, [wsContext, clearStreamStartWatchdog, streamType, acceptsStreamType, logPrefix, streamEpochRef, handleStreamStartRef]);

  // The next connection may reach a restarted backend whose epoch count starts
  // over, so the ordering guard above must not compare across connections.
  useEffect(() => {
    if (!wsContext.isConnected) streamEpochRef.current = null;
  }, [wsContext.isConnected, streamEpochRef]);

}
