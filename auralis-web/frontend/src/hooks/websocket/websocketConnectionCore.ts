/**
 * websocketConnectionCore - transport singletons + pure framing helpers
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * The React-free core of the single WebSocket connection, split out of
 * `useWebSocketConnection` (#4297) so both files stay under the 300-line
 * convention. Holds the module-level singleton state (one connection across
 * StrictMode remounts) and the two pure procedures that operate on it:
 * inbound-frame parsing and the on-reconnect queue replay / stream resume.
 */

import { WebSocketManager } from '@/utils/errorHandling';
import type {
  AnyWebSocketMessage,
  AudioChunkMessage,
  AudioChunkMetaMessage,
  WebSocketMessage,
} from '@/types/websocket';

// ============================================================================
// Public types
// ============================================================================

export interface OutgoingWebSocketMessage {
  type: string;
  data?: Record<string, unknown>;
}

export type ConnectionStatus = 'connected' | 'connecting' | 'disconnected' | 'error';

/** Dispatch a parsed inbound message to subscribers (owned by the provider). */
export type DispatchMessage = (message: AnyWebSocketMessage | WebSocketMessage) => void;

// ============================================================================
// Singleton connection state (survives StrictMode double-mounting)
// ============================================================================

/**
 * Module-level singleton state so only ONE WebSocket connection exists even
 * when StrictMode double-mounts the provider in development. A single mutable
 * container (rather than several `let` bindings) lets the pure helpers below
 * — which live in this module — share the state with the hook.
 *
 * - `manager` / `refCount`: the connection and how many providers hold it.
 * - `url`: the URL `manager` was built for, so a URL change can be detected and
 *   the old socket torn down instead of silently orphaned (#4522).
 * - `connectPromise`: the in-flight `manager.connect()` handshake. Concurrent
 *   callers await this one promise rather than each building their own manager
 *   (#4522) — the window is the whole handshake plus every reconnect backoff,
 *   up to 30 s per attempt.
 * - `pendingMeta`: an audio_chunk_meta text frame awaiting its binary PCM frame.
 * - `lastStreamCommand`: last play_enhanced/play_normal, re-issued on reconnect
 *   (#2385); cleared on explicit stop/pause.
 * - `resumeGetters`: per-stream-type playback-position getters (#3185/#3373).
 */
export interface ConnectionState {
  manager: WebSocketManager | null;
  url: string | null;
  connectPromise: Promise<void> | null;
  refCount: number;
  pendingMeta: AudioChunkMetaMessage | null;
  lastStreamCommand: OutgoingWebSocketMessage | null;
  resumeGetters: Record<string, () => number>;
}

export const connState: ConnectionState = {
  manager: null,
  url: null,
  connectPromise: null,
  refCount: 0,
  pendingMeta: null,
  lastStreamCommand: null,
  resumeGetters: {},
};

/**
 * Tear down the current singleton manager, if any, before it is replaced or
 * dropped (#4522).
 *
 * Every path that clears or overwrites `connState.manager` must go through
 * here. Dropping the reference alone leaves the old socket, its handlers and
 * its running reconnect timer alive and unreachable — nothing else holds a
 * reference to close them, so it keeps dispatching inbound frames into Redux
 * for the lifetime of the renderer.
 */
export function closeCurrentManager(): void {
  if (connState.manager) {
    try {
      connState.manager.close();
    } catch {
      // Ignore errors during teardown
    }
  }
  connState.manager = null;
  connState.url = null;
  connState.connectPromise = null;
}

/**
 * Reset the connection singletons — ONLY FOR TESTING. Called by the provider's
 * resetWebSocketSingletons() (which also clears the subscription maps) between
 * tests to prevent memory leaks from accumulated connections.
 */
export function resetConnectionSingletons(): void {
  // Also clears `url` and `connectPromise` (#4522) — a leaked connectPromise
  // would make the next test's first connect() await a dead handshake.
  closeCurrentManager();
  connState.refCount = 0;
  connState.lastStreamCommand = null;
  for (const key of Object.keys(connState.resumeGetters)) {
    delete connState.resumeGetters[key];
  }
  connState.pendingMeta = null;
}

// ============================================================================
// Pure procedures
// ============================================================================

/**
 * Parse one inbound frame and dispatch it. Handles the backend's binary PCM
 * protocol (an `audio_chunk_meta` text frame immediately followed by a raw
 * ArrayBuffer/Blob PCM frame → recombined into a single `audio_chunk`), the
 * server heartbeat (`ping` → `pong`), and plain JSON messages.
 */
export function handleSocketFrame(
  event: MessageEvent,
  manager: WebSocketManager,
  dispatch: DispatchMessage
): void {
  try {
    // Binary frame: raw PCM data following an audio_chunk_meta message
    if (event.data instanceof ArrayBuffer) {
      if (connState.pendingMeta) {
        // Attach the binary payload to the pending metadata and dispatch
        // as an 'audio_chunk' message so existing subscribers work unchanged.
        const combined: AudioChunkMessage = {
          type: 'audio_chunk',
          data: {
            ...connState.pendingMeta.data,
            pcm_binary: event.data,
          },
        };
        connState.pendingMeta = null;
        dispatch(combined);
      } else {
        console.warn('[WebSocket] Received binary frame without preceding audio_chunk_meta');
      }
      return;
    }

    // Handle Blob data (some browsers send binary as Blob)
    if (event.data instanceof Blob) {
      // Capture AND clear synchronously: the pending meta belongs to THIS blob
      // (it always arrives immediately after its audio_chunk_meta text frame).
      // Nulling inside the async .then() would instead clear whatever is pending
      // when the promise resolves — which may be the NEXT chunk's meta if its
      // text frame arrived while arrayBuffer() was still decoding, dropping that
      // chunk (#4331). This mirrors the synchronous ArrayBuffer path above.
      const meta = connState.pendingMeta;
      connState.pendingMeta = null;
      event.data.arrayBuffer().then((buffer: ArrayBuffer) => {
        if (meta) {
          const combined: AudioChunkMessage = {
            type: 'audio_chunk',
            data: {
              ...meta.data,
              pcm_binary: buffer,
            },
          };
          dispatch(combined);
        }
      });
      return;
    }

    // Text frame: JSON message. AudioChunkMetaMessage is included here (though
    // not part of the public AnyWebSocketMessage union, #4167) because the
    // backend still sends it and we consume it internally.
    const message: AnyWebSocketMessage | WebSocketMessage | AudioChunkMetaMessage =
      JSON.parse(event.data);

    // If this is an audio_chunk_meta, stash it and wait for the binary frame.
    // It is never dispatched to subscribers.
    if (message.type === 'audio_chunk_meta') {
      connState.pendingMeta = message;
      return;
    }

    // The meta+binary frame pair is not sent atomically (#4782): if the
    // server sends audio_chunk_meta successfully but the following binary
    // PCM frame then fails to send, pendingMeta above is left set with
    // nothing to clear it — the NEXT binary frame that arrives (from a
    // later, unrelated chunk or stream) gets silently fused with this stale
    // metadata instead. Every live chunk-delivery path on the backend sends
    // audio_stream_error whenever a chunk fails to fully deliver, so treat
    // any stream error as a signal to drop whatever frame pairing was in
    // flight — covers both the ArrayBuffer and Blob paths above, since both
    // read the same `pendingMeta` slot.
    if (message.type === 'audio_stream_error' && connState.pendingMeta) {
      console.warn('[WebSocket] Clearing stale pendingMeta after audio_stream_error');
      connState.pendingMeta = null;
    }

    // Answer the server heartbeat. The backend arms a pending-pong on every
    // `ping` and force-closes the socket (~60s) if no `pong` clears it; a
    // `heartbeat` frame only touches liveness, not the pending-pong slot, so it
    // never clears the armed ping (#4406).
    if ((message.type as string) === 'ping') {
      try {
        manager.send(JSON.stringify({ type: 'pong' }));
      } catch (err) {
        console.warn('[WebSocket] Failed to reply pong to server ping:', err);
      }
      return;
    }

    dispatch(message);
  } catch (error) {
    console.error('Failed to parse WebSocket message:', error);
  }
}

/**
 * On (re)connect: flush the offline send-queue, then re-issue the last active
 * stream so audio resumes after a drop (#2385) from the current playback
 * position (#3185). Skips the re-issue if the queue already carried a fresh
 * play/stop command, so a stale play is not replayed over it (#3345).
 */
export function replayQueueAndResume(
  manager: WebSocketManager,
  queue: OutgoingWebSocketMessage[]
): void {
  // Send queued messages (commands sent while disconnected). Track whether any
  // queued message supersedes the saved stream command so we don't re-issue a
  // stale play after reconnect (#3345).
  let queueHadStreamCommand = false;
  while (queue.length > 0) {
    const message = queue.shift();
    if (message?.type === 'play_enhanced' || message?.type === 'play_normal') {
      connState.lastStreamCommand = message;
      queueHadStreamCommand = true;
    } else if (message?.type === 'stop' || message?.type === 'pause') {
      connState.lastStreamCommand = null;
      queueHadStreamCommand = true;
    }
    manager.send(JSON.stringify(message));
  }

  if (connState.lastStreamCommand && !queueHadStreamCommand) {
    const resumePos = connState.resumeGetters[connState.lastStreamCommand.type]?.() ?? 0;
    const resumeCommand = {
      ...connState.lastStreamCommand,
      data: {
        ...(connState.lastStreamCommand.data ?? {}),
        start_position: resumePos,
      },
    };
    console.log(`🔄 Reconnected - re-issuing stream command: ${connState.lastStreamCommand.type} at ${resumePos.toFixed(1)}s`);
    manager.send(JSON.stringify(resumeCommand));
  }
}
