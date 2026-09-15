/**
 * PCM Decoding Utilities
 *
 * Decodes PCM samples from WebSocket audio_chunk messages into Float32Array
 * for playback via Web Audio API.
 *
 * Supports two transport modes:
 * - Binary: raw PCM bytes via binary WebSocket frames (preferred, zero-copy)
 * - Base64: base64-encoded PCM in JSON text messages (legacy fallback)
 *
 * Handles:
 * - ArrayBuffer to Float32 PCM conversion (binary mode)
 * - Base64 to binary conversion (legacy mode)
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
 * This is the preferred path — no base64 encode/decode overhead.
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
 * Decode base64-encoded PCM samples to Float32Array
 *
 * Legacy path: PCM samples encoded as base64 in JSON WebSocket messages.
 * Prefer decodeBinaryPCM() for binary frames.
 *
 * @param base64Data Base64-encoded PCM samples (from WebSocket message)
 * @returns Float32Array of decoded PCM samples
 * @throws Error if base64 data is invalid or too short
 *
 * @example
 * const pcm = decodePCMBase64("AQIDBA=="); // 4-byte PCM data
 * console.log(pcm); // Float32Array with decoded samples
 */
export function decodePCMBase64(base64Data: string): Float32Array {
  try {
    // Decode base64 to binary string
    const binaryString = atob(base64Data);

    // Convert binary string to Uint8Array
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }

    // Convert bytes to Float32Array
    // Each float32 sample = 4 bytes
    const sampleCount = bytes.length / 4;
    if (bytes.length % 4 !== 0) {
      throw new Error(
        `PCM data size (${bytes.length}) not divisible by 4 (float32 sample size)`
      );
    }

    const dataView = new DataView(bytes.buffer);
    const pcmSamples = new Float32Array(sampleCount);

    for (let i = 0; i < sampleCount; i++) {
      // Read as little-endian float32
      pcmSamples[i] = dataView.getFloat32(i * 4, true);
    }

    return pcmSamples;
  } catch (error) {
    if (error instanceof Error) {
      throw new Error(`Failed to decode PCM base64: ${error.message}`);
    }
    throw error;
  }
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
 * Supports two transport modes:
 * - Binary (preferred): `data.pcm_binary` is an ArrayBuffer of raw float32 PCM
 * - Base64 (legacy): `data.samples` is a base64-encoded string
 *
 * @param message WebSocket message object with data and type
 * @param sampleRate Expected sample rate
 * @param channels Expected channel count
 * @returns Decoded PCM samples and metadata
 * @throws Error if message format is invalid
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

  // Decode PCM: prefer binary ArrayBuffer, fall back to base64 string
  let samples: Float32Array;
  try {
    if (data.pcm_binary instanceof ArrayBuffer) {
      samples = decodeBinaryPCM(data.pcm_binary);
    } else if (data.samples && typeof data.samples === 'string') {
      samples = decodePCMBase64(data.samples);
    } else {
      throw new Error('Missing PCM data: no pcm_binary or samples field');
    }
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
