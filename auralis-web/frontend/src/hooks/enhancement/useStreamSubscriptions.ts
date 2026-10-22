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

import { useEffect } from 'react';
import type { useWebSocketContext } from '@/contexts/WebSocketContext';
import { useMessageSubscriptions } from '@/hooks/websocket/useWebSocketMessages';
import type {
  AudioStreamStartMessage,
  AudioChunkMessage,
  AudioStreamEndMessage,
  AudioStreamErrorMessage,
} from '@/contexts/WebSocketContext';
import type { StreamType } from './streamingCoreTypes';

export interface StreamSubscriptionDeps {
  wsContext: ReturnType<typeof useWebSocketContext>;

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
    logPrefix,
    streamEpochRef,
    handleStreamStartRef,
    acceptsStreamType,
    clearStreamStartWatchdog,
    handleChunk,
    handleStreamEnd,
    handleStreamError,
  } = deps;

  // Handler identity changes never resubscribe (the shared hook holds them in a
  // ref, #3588/#2532). handleStreamStartRef is populated by the caller
  // (`core.handleStreamStartRef.current = handleStreamStart`) since it's
  // defined hook-side, not by this core.
  // Any incoming stream message means the backend is responding, so every
  // handler first disarms the first-stream watchdog (#4433).
  //
  // The shared hook holds these handlers in a ref and resubscribes only when
  // `subscribe` changes (#4668, #5621): the context object's identity changes
  // with every isConnected/connectionStatus flicker, and tearing down and
  // re-registering all four subscriptions used to disarm the stream-start
  // watchdog on the way. It deliberately does NOT clear the watchdog on
  // cleanup either — useStreamStartWatchdog owns unmount cleanup, and a
  // resubscribe across a status flap must not disarm one that is mid-flight.
  useMessageSubscriptions(wsContext.subscribe, {
    audio_stream_start: (m) => {
      clearStreamStartWatchdog();
      const start = m as unknown as AudioStreamStartMessage;
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
    },
    audio_chunk: (m) => { clearStreamStartWatchdog(); handleChunk(m as unknown as AudioChunkMessage); },
    audio_stream_end: (m) => { clearStreamStartWatchdog(); handleStreamEnd(m as unknown as AudioStreamEndMessage); },
    audio_stream_error: (m) => { clearStreamStartWatchdog(); handleStreamError(m as unknown as AudioStreamErrorMessage); },
  });

  // The next connection may reach a restarted backend whose epoch count starts
  // over, so the ordering guard above must not compare across connections.
  useEffect(() => {
    if (!wsContext.isConnected) streamEpochRef.current = null;
  }, [wsContext.isConnected, streamEpochRef]);

}
