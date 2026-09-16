/**
 * PCM Decoding Utilities
 *
 * Decodes PCM samples from WebSocket audio_chunk messages into Float32Array
 * for playback via Web Audio API.
 *
 * Transport: raw PCM bytes via binary WebSocket frames (zero-copy). The
 * base64-in-JSON fallback (#2764/#3944) was removed in #5423 — the backend
 * has emitted binary frames exclusively for years, and Auralis ships
 * frontend and backend as one Electron bundle, so there is no
 * independently-versioned legacy client that could still send base64.
 *
 * Handles:
 * - ArrayBuffer to Float32 PCM conversion
 * - Sample rate and channel metadata
 *
 * #5392: monoToStereo, stereoInterleavedToChannels, resamplePCM,
 * durationToSampleCount, sampleCountToDuration, validatePCMSamples and
 * clipPCMSamples were deleted — only their own tests called them. No
 * client-side validate/clip pass was wired in instead: the backend is the
 * sample-integrity authority, and its realtime chain already replaces
 * non-finite output before emission (#5313).
 */

import type { AudioChunkMessage } from '@/types/websocket';

/**
 * Decode raw PCM bytes from an ArrayBuffer to Float32Array (zero-copy path)
 *
 * Used when backend sends binary WebSocket frames containing raw float32 PCM.
 *
 * @param buffer ArrayBuffer containing raw float32 PCM bytes
 * @returns Float32Array view of the PCM data
 * @throws Error if buffer size is not divisible by 4
 */
export function decodeBinaryPCM(buffer: ArrayBuffer): Float32Array {
  if (buffer.byteLength % 4 !== 0) {
    throw new Error(
      `PCM binary data size (${buffer.byteLength}) not divisible by 4 (float32 sample size)`
    );
  }
  return new Float32Array(buffer);
}

/**
 * Type for PCM metadata from audio_chunk WebSocket message
 */
export interface PCMChunkMetadata {
  sampleRate: number;
  channels: number;
  chunkIndex: number;
  chunkCount: number;
  frameIndex: number;
  frameCount: number;
  sampleCount: number;
}

/**
 * Decode a complete audio_chunk WebSocket message
 *
 * `data.pcm_binary` must be an ArrayBuffer of raw float32 PCM (#5423).
 *
 * @param message WebSocket message object with data and type
 * @param sampleRate Expected sample rate
 * @param channels Expected channel count
 * @returns Decoded PCM samples and metadata
 * @throws Error if message format is invalid or `pcm_binary` is missing
 */
export function decodeAudioChunkMessage(
  message: AudioChunkMessage,
  sampleRate: number,
  channels: number
): {
  samples: Float32Array;
  metadata: PCMChunkMetadata;
} {
  if (!message || !message.data) {
    throw new Error('Invalid audio_chunk message format');
  }

  const data = message.data;

  if (data.sample_count === undefined || data.sample_count <= 0) {
    throw new Error('Invalid sample_count in audio_chunk');
  }

  // #5423: no fallback -- a frame missing pcm_binary is malformed, not a
  // legacy client, and must fail loudly rather than risk decoding a stray
  // `samples` string as base64 garbage.
  let samples: Float32Array;
  try {
    if (!(data.pcm_binary instanceof ArrayBuffer)) {
      throw new Error('Missing PCM data: no pcm_binary field');
    }
    samples = decodeBinaryPCM(data.pcm_binary);
  } catch (error) {
    throw new Error(
      `Failed to decode PCM samples: ${error instanceof Error ? error.message : String(error)}`
    );
  }

  // Validate decoded sample count matches expected
  if (samples.length !== data.sample_count) {
    console.warn(
      `Sample count mismatch: decoded ${samples.length}, expected ${data.sample_count}`
    );
  }

  // Build metadata
  const metadata: PCMChunkMetadata = {
    sampleRate,
    channels,
    chunkIndex: data.chunk_index ?? 0,
    chunkCount: data.chunk_count ?? 1,
    frameIndex: data.frame_index ?? 0,
    frameCount: data.frame_count ?? 1,
    sampleCount: samples.length,
  };

  return { samples, metadata };
}
