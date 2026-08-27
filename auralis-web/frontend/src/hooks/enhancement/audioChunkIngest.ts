/**
 * Audio chunk ingest — the decode/append half of useAudioStreamingCore's
 * per-chunk hot path, as a plain function (#5041).
 *
 * `handleChunk` had grown to ~144 lines and ran on every `audio_chunk`
 * message during playback, so the busiest code in the streaming client was
 * also the least testable: exercising it at all meant mounting React via
 * `renderHook`.
 *
 * The split is deliberately drawn at the side-effect boundary. Everything
 * here is a decision *about* the chunk — should it be dropped, what does the
 * buffer now hold, has progress moved far enough to be worth a Redux
 * dispatch, is there enough audio to start playing. Acting on those decisions
 * (dispatching, sending flow-control frames over the WebSocket, starting the
 * engine) stays in the hook, because that is where the React refs and the
 * `StreamingCoreOptions` live.
 *
 * The two mutable collaborators — the PCM buffer and the metadata record —
 * are passed in rather than reached for, so a test can hand in fakes.
 *
 * @module hooks/enhancement/audioChunkIngest
 */

import type PCMStreamBuffer from '@/services/audio/PCMStreamBuffer';
import { decodeAudioChunkMessage } from '@/utils/audio/pcmDecoding';
import type { AudioChunkMessage } from '@/contexts/WebSocketContext';
import type { StreamingMetadata, StreamType } from './useAudioStreamingCore';

/** Buffer fill (%) at which we ask the backend to stop sending. */
export const FLOW_PAUSE_FILL_PCT = 75;
/** Buffer fill (%) at which we ask it to resume. The 25-point gap is
 *  hysteresis — without it the two frames ping-pong every chunk. */
export const FLOW_RESUME_FILL_PCT = 50;

/** Why `classifyChunk` rejected a message, or `null` to keep processing. */
export type ChunkRejection =
  /** Belongs to a different stream type (#2104). */
  | 'wrong-stream-type'
  /** From a stream this client has already superseded via seek (#4563). */
  | 'superseded-epoch'
  /** Stream not initialized yet — the caller should queue, not drop. */
  | 'not-initialized';

export interface ClassifyChunkArgs {
  message: AudioChunkMessage;
  /** Current stream epoch, or null when this client has none yet. */
  currentEpoch: number | null;
  /** Whether the stream's buffer + metadata are both ready. */
  initialized: boolean;
  acceptsStreamType: (incoming: StreamType | undefined) => boolean;
}

/**
 * Decide whether a chunk should be processed, queued, or dropped.
 *
 * The epoch check is the only thing that distinguishes pre-seek audio still
 * in flight from the post-seek stream (#4563): the track_id matches, the
 * chunk_index is not lower so the out-of-sequence guard never trips, and
 * `is_seek: true` deliberately preserves the buffer. Both sides must carry an
 * epoch, so a backend that does not send one degrades to the old behaviour
 * rather than dropping everything.
 */
export function classifyChunk({
  message,
  currentEpoch,
  initialized,
  acceptsStreamType,
}: ClassifyChunkArgs): ChunkRejection | null {
  if (!acceptsStreamType(message.data.stream_type)) return 'wrong-stream-type';

  const incomingEpoch = message.data.stream_epoch;
  if (incomingEpoch != null && currentEpoch != null && incomingEpoch !== currentEpoch) {
    return 'superseded-epoch';
  }

  if (!initialized) return 'not-initialized';

  return null;
}

/**
 * Decide whether an incoming chunk index indicates a stream restart.
 *
 * A chunk index that jumps *backwards* by more than one means a new stream
 * began without an `audio_stream_start` — e.g. one missed during a WebSocket
 * reconnect. The buffer has to be reset or the old and new audio interleave.
 */
export function isOutOfSequence(lastChunkIndex: number, incomingChunkIndex: number): boolean {
  return lastChunkIndex >= 0 && incomingChunkIndex < lastChunkIndex - 1;
}

/** What the caller should do about backend flow control after this chunk. */
export type FlowControlSignal = 'pause' | 'resume' | null;

export function nextFlowControlSignal(
  fillPercentage: number,
  currentlyPaused: boolean
): FlowControlSignal {
  if (fillPercentage > FLOW_PAUSE_FILL_PCT && !currentlyPaused) return 'pause';
  if (fillPercentage < FLOW_RESUME_FILL_PCT && currentlyPaused) return 'resume';
  return null;
}

/**
 * Whether a progress value is worth a Redux dispatch.
 *
 * Unthrottled, this fires once per sub-frame — O(n_chunks) store churn for a
 * bar that moves in whole percents (#2535). First chunk, each 10% decile, and
 * completion are enough.
 */
export function shouldDispatchProgress(
  clampedProgress: number,
  lastDispatchedProgress: number,
  throttle: boolean
): boolean {
  if (!throttle) return true;
  if (lastDispatchedProgress < 0) return true;
  if (clampedProgress >= 100) return true;
  return (
    Math.floor(clampedProgress / 10) > Math.floor(Math.max(0, lastDispatchedProgress) / 10)
  );
}

export interface IngestChunkArgs {
  message: AudioChunkMessage;
  buffer: PCMStreamBuffer;
  /** Mutated in place: `processedChunks` advances as content chunks land. */
  metadata: StreamingMetadata;
  flowPaused: boolean;
}

export interface IngestChunkResult {
  /** Samples now readable from the buffer. */
  bufferedSamples: number;
  /** Completion percentage, clamped to 100. */
  clampedProgress: number;
  /** Flow-control frame the caller should send, if any. */
  flowControl: FlowControlSignal;
  /** Decoder metadata, for the caller's debug logging. */
  chunkIndex: number;
  frameIndex: number;
  frameCount: number;
  sampleCount: number;
}

/**
 * Decode a chunk, append it to the buffer, and report the resulting state.
 *
 * `metadata.processedChunks` advances once per *content* chunk, on its final
 * frame — not once per message. The backend splits each content chunk into
 * ~300 KB binary sub-frames that each arrive as their own `audio_chunk`, so
 * counting messages ran the numerator 12-18x too fast against the
 * `total_chunks` from `audio_stream_start` and the bar hit 100% during the
 * first chunk (#4414). `frameCount` defaults to 1 in the decoder, so
 * single-frame chunks still increment exactly once.
 */
export function ingestChunk({
  message,
  buffer,
  metadata,
  flowPaused,
}: IngestChunkArgs): IngestChunkResult {
  const { samples, metadata: chunkMeta } = decodeAudioChunkMessage(
    message,
    metadata.sampleRate,
    metadata.channels
  );

  buffer.append(samples);

  const flowControl = nextFlowControlSignal(buffer.getFillPercentage(), flowPaused);

  if (chunkMeta.frameIndex >= chunkMeta.frameCount - 1) {
    metadata.processedChunks++;
  }

  const bufferedSamples = buffer.getAvailableSamples();
  const clampedProgress = Math.min(
    (metadata.processedChunks / metadata.totalChunks) * 100,
    100
  );

  return {
    bufferedSamples,
    clampedProgress,
    flowControl,
    chunkIndex: chunkMeta.chunkIndex,
    frameIndex: chunkMeta.frameIndex,
    frameCount: chunkMeta.frameCount,
    sampleCount: chunkMeta.sampleCount,
  };
}
