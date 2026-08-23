/**
 * WebSocket message types — streaming domain.
 * Split from the former monolithic types/websocket.ts (#4081); consumers import
 * via the '@/types/websocket' barrel which re-exports every ws/* module.
 */


import type { EnhancementPreset } from '@/types/domain';
import type { WebSocketMessage } from './base';

/** Message-type literals owned by the streaming domain.
 *
 * Note: 'audio_chunk_meta' is intentionally NOT here. It is a text frame that
 * WebSocketContext consumes internally (pairing it with the following binary
 * PCM frame into a synthesised 'audio_chunk'); it is never dispatched, so it is
 * not a public subscription key (#4167). Its shape is AudioChunkMetaMessage. */
export type StreamingMessageType =
  | 'audio_stream_start'
  | 'audio_stream_end'
  | 'audio_chunk'
  | 'audio_stream_error';


// ============================================================================
// Audio Stream Messages (fixes #2282)
// ============================================================================

/** Sent when a new audio stream begins (fixes #2503) */
export interface AudioStreamStartMessage extends WebSocketMessage {
  type: 'audio_stream_start';
  data: {
    track_id: number;
    preset: EnhancementPreset;
    intensity: number;
    sample_rate: number;
    channels: number;
    total_chunks: number;
    chunk_duration: number;
    total_duration: number;
    stream_type?: 'enhanced' | 'normal';
    /**
     * Monotonic id for this stream (#4563). Record it on stream start and drop
     * any `audio_chunk` whose `stream_epoch` differs: cancelling a superseded
     * stream is asynchronous with respect to frames already in the send queue
     * and socket buffers, and `is_seek: true` tells the client to preserve its
     * buffer, so without this those stale frames play at the head of the seek.
     */
    stream_epoch?: number;
    is_seek?: boolean;
    start_chunk?: number;
    seek_position?: number;
    /**
     * Within-chunk offset of `seek_position`, in seconds.
     *
     * INFORMATIONAL ONLY — the server trims the first chunk itself on both the
     * enhanced (`stream_seek.py`) and normal (`stream_normal.py`) paths, so the
     * first delivered sample already corresponds to `seek_position` (#4560). Do
     * NOT trim by this value client-side; that would double-skip.
     */
    seek_offset?: number;
  };
}


export interface AudioStreamEndMessage extends WebSocketMessage {
  type: 'audio_stream_end';
  data: {
    track_id: number;
    total_samples?: number;
    duration?: number;
    stream_type?: 'enhanced' | 'normal';
    /** Why the stream ended (#4659, #4790).
     *
     * `'completed'` — the chunk loop delivered the whole track.
     * `'stopped'`   — it exited early (e.g. enhancement toggled off mid-stream),
     *                 in which case `total_samples`/`duration` describe what was
     *                 actually delivered, NOT the full track.
     * `'errored'`   — the chunk loop ran to its natural end, but one or more
     *                 chunks failed processing and were skipped (#4790) — the
     *                 stream has gaps (or, if every chunk failed, delivered no
     *                 audio at all). `total_samples`/`duration` describe what
     *                 was actually delivered, NOT the full track. Distinct from
     *                 `'stopped'` so a client can tell "stopped by user/backend"
     *                 apart from "aborted by chunk failures".
     *
     * Optional so pre-#4659 backends (which always sent a success-shaped end
     * message) still type-check; treat a missing value as `'completed'`.
     */
    reason?: 'completed' | 'stopped' | 'errored';
  };
}


/** Sent for each PCM audio chunk during streaming (fixes #2501).
 *
 * Note: in production the backend emits {@link AudioChunkMetaMessage}
 * (a text JSON frame) followed by a binary PCM frame. WebSocketContext
 * fuses them into this synthetic `audio_chunk` shape with `pcm_binary`
 * populated. The `samples` base64 path remains for legacy clients only.
 */
export interface AudioChunkMessage extends WebSocketMessage {
  type: 'audio_chunk';
  data: {
    /** Monotonic sequence counter carried over from audio_chunk_meta (fixes #3944 / TS-2).
     *  Consumers can detect dropped or reordered frames by checking seq increments by 1. */
    seq?: number;
    /** Owning track id, carried over from audio_chunk_meta so consumers can drop
     *  late chunk-progress from a superseded track after a rapid skip (#4434). */
    track_id?: number;
    /** Owning stream epoch, carried over from audio_chunk_meta. Frames whose
     *  epoch differs from the one on the current audio_stream_start belong to a
     *  stream that a seek/stop already superseded and must be dropped (#4563). */
    stream_epoch?: number;
    chunk_index: number;
    chunk_count: number;
    frame_index: number;
    frame_count: number;
    /** Base64-encoded float32 PCM (legacy transport). Optional because the
     *  binary transport path (pcm_binary) does not include this field (#3944). */
    samples?: string;
    sample_count: number;
    stream_type?: 'enhanced' | 'normal';
    /** Raw float32 PCM ArrayBuffer (binary transport, preferred over base64). Injected
     *  at runtime by WebSocketContext when a binary frame follows audio_chunk_meta (fixes #2764). */
    pcm_binary?: ArrayBuffer;
  };
}


/** Text-frame metadata that precedes each binary PCM chunk (#3506 / BE-NEW-48).
 *  The backend emits this in _send_pcm_chunk before the matching binary frame.
 *  WebSocketContext pairs the two and synthesises an `audio_chunk` event for
 *  downstream consumers — direct consumers of this raw shape should read seq /
 *  frame_index for desync detection.
 *
 *  INTERNAL: deliberately does NOT extend WebSocketMessage and 'audio_chunk_meta'
 *  is not a WebSocketMessageType — this message is consumed by WebSocketContext
 *  and never dispatched, so it is not a public subscription key (#4167). */
export interface AudioChunkMetaMessage {
  type: 'audio_chunk_meta';
  timestamp?: number;
  data: {
    /** Monotonic sequence counter across the entire stream — clients can
     *  detect dropped or reordered frames by checking that seq increases
     *  by exactly 1 per frame (fixes #3189). */
    seq: number;
    /** Owning track id so the client can drop late chunk-progress from a
     *  superseded track after a rapid skip (#4434). */
    track_id?: number;
    /** Owning stream epoch (#4563) — see AudioChunkMessage.stream_epoch. */
    stream_epoch?: number;
    chunk_index: number;
    chunk_count: number;
    frame_index: number;
    frame_count: number;
    sample_count: number;
    stream_type?: 'enhanced' | 'normal';
  };
}


export interface AudioStreamErrorMessage extends WebSocketMessage {
  type: 'audio_stream_error';
  data: {
    track_id: number;
    error: string;
    code?: string;
    stream_type?: 'enhanced' | 'normal';
    /** When the backend can suggest where to resume (e.g. start of the
     *  failed chunk or the user's seek target), it sets this seconds-offset
     *  so the client can offer a 'retry from here' (#3547 / BE-NEW-89,
     *  also exposed at audio_stream_controller.py per #2085). */
    recovery_position?: number;
  };
}
