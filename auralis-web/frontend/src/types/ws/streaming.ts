/**
 * WebSocket message types — streaming domain.
 * Split from the former monolithic types/websocket.ts (#4081); consumers import
 * via the '@/types/websocket' barrel which re-exports every ws/* module.
 */


import type { EnhancementPreset } from '../domain';
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
    is_seek?: boolean;
    start_chunk?: number;
    seek_position?: number;
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
    chunk_index: number;
    chunk_count: number;
    frame_index: number;
    frame_count: number;
    /** Base64-encoded float32 PCM (legacy transport). Optional because the
     *  binary transport path (pcm_binary) does not include this field (#3944). */
    samples?: string;
    sample_count: number;
    crossfade_samples: number;
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
    chunk_index: number;
    chunk_count: number;
    frame_index: number;
    frame_count: number;
    sample_count: number;
    crossfade_samples: number;
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
