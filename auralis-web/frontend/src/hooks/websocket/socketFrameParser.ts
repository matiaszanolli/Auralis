/**
 * socketFrameParser - inbound WebSocket frame parsing
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Split out of websocketConnectionCore.ts (#5840). Pairs the backend's binary
 * PCM protocol, answers the heartbeat, and checks `audio_chunk_meta.seq` for
 * desync, operating on the shared `connState`.
 */

import type { WebSocketManager } from '@/utils/errorHandling';
import type {
  AnyWebSocketMessage,
  AudioChunkMessage,
  AudioChunkMetaMessage,
  AudioStreamErrorMessage,
  WebSocketMessage,
} from '@/types/websocket';
import { connState, type DispatchMessage } from './websocketConnectionState';

/**
 * Validate `audio_chunk_meta.seq` against the running per-stream counter
 * (#3774). The backend stamps a monotonic `seq` on every `audio_chunk_meta`
 * specifically so a dropped or reordered WS frame (proxy hiccup, browser
 * throttle, GC pause) can be detected — before this, nothing read it, so the
 * guarantee was nominal only and a desync would silently pair the wrong PCM
 * with the wrong meta.
 *
 * Tracking resets on a new `stream_epoch` (seek/track change starts a fresh
 * stream, #4563) so the counter never compares across unrelated streams. A
 * gap dispatches a synthetic `audio_stream_error`, reusing the exact handling
 * path (`useAudioStreamingCore.handleStreamError`) a server-detected error
 * already goes through — visible error state + stream cleanup — rather than
 * inventing a second, parallel recovery mechanism.
 */
function checkSeqForDesync(meta: AudioChunkMetaMessage, dispatch: DispatchMessage): void {
  const { seq, stream_epoch, track_id, stream_type } = meta.data;
  if (typeof seq !== 'number') return;

  if (stream_epoch !== connState.seqStreamEpoch) {
    connState.seqStreamEpoch = stream_epoch ?? null;
    connState.expectedSeq = null;
  }

  if (connState.expectedSeq !== null && seq !== connState.expectedSeq) {
    console.warn(
      `[WebSocket] audio_chunk_meta desync: expected seq ${connState.expectedSeq}, got ${seq} ` +
      `(stream_epoch=${stream_epoch ?? 'none'})`
    );
    const desyncError: AudioStreamErrorMessage = {
      type: 'audio_stream_error',
      data: {
        track_id: track_id ?? 0,
        error: `Audio stream desync detected (expected frame ${connState.expectedSeq}, got ${seq})`,
        code: 'DESYNC',
        stream_type,
      },
    };
    dispatch(desyncError);
    // Resync on the frame we just saw rather than re-firing every
    // subsequent frame until the next gap.
  }

  connState.expectedSeq = seq + 1;
}

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
    // It is never dispatched to subscribers (except the synthetic desync
    // audio_stream_error below).
    if (message.type === 'audio_chunk_meta') {
      const meta = message as AudioChunkMetaMessage;
      checkSeqForDesync(meta, dispatch);
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
