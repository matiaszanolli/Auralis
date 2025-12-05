/**
 * PCM Decoding Utilities
 *
 * Decodes base64-encoded PCM samples from WebSocket audio_chunk messages
 * into Float32Array for playback via Web Audio API.
 *
 * Handles:
 * - Base64 to binary conversion
 * - Binary to Float32 PCM conversion
 * - Channel layout conversion (mono to stereo, etc.)
 * - Sample rate and channel metadata
 */

/**
 * Decode base64-encoded PCM samples to Float32Array
 *
 * PCM samples are encoded as base64 in WebSocket messages to minimize bandwidth.
 * This function reverses that encoding for playback.
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
 * Convert mono PCM to stereo by duplicating the channel
 *
 * @param mono Float32Array with mono samples
 * @returns Float32Array with stereo samples (L,R,L,R,...)
 *
 * @example
 * const mono = new Float32Array([0.1, 0.2, 0.3]);
 * const stereo = monoToStereo(mono);
 * // stereo = [0.1, 0.1, 0.2, 0.2, 0.3, 0.3]
 */
export function monoToStereo(mono: Float32Array): Float32Array {
  const stereo = new Float32Array(mono.length * 2);
  for (let i = 0; i < mono.length; i++) {
    stereo[i * 2] = mono[i];     // Left channel
    stereo[i * 2 + 1] = mono[i]; // Right channel
  }
  return stereo;
}

/**
 * Convert stereo interleaved PCM to separate channel arrays
 *
 * Interleaved format: L,R,L,R,L,R,...
 * Output: [left_array, right_array]
 *
 * @param interleaved Float32Array with interleaved stereo samples
 * @returns Tuple of [left, right] channel arrays
 * @throws Error if sample count is not even
 *
 * @example
 * const stereo = new Float32Array([0.1, 0.2, 0.3, 0.4]);
 * const [left, right] = stereoInterleavedToChannels(stereo);
 * // left = [0.1, 0.3], right = [0.2, 0.4]
 */
export function stereoInterleavedToChannels(
  interleaved: Float32Array
): [Float32Array, Float32Array] {
  if (interleaved.length % 2 !== 0) {
    throw new Error(
      `Stereo interleaved PCM must have even sample count, got ${interleaved.length}`
    );
  }

  const sampleCount = interleaved.length / 2;
  const left = new Float32Array(sampleCount);
  const right = new Float32Array(sampleCount);

  for (let i = 0; i < sampleCount; i++) {
    left[i] = interleaved[i * 2];
    right[i] = interleaved[i * 2 + 1];
  }

  return [left, right];
}

/**
 * Validate PCM samples are within valid range and finite
 *
 * Audio samples should be in [-1.0, 1.0] range for float32 PCM.
 * Values outside this range may cause clipping or distortion.
 *
 * @param samples Float32Array to validate
 * @returns true if all samples are finite and in valid range
 *
 * @example
 * const pcm = new Float32Array([0.1, 0.5, -0.3]);
 * if (!validatePCMSamples(pcm)) {
 *   console.warn('PCM samples out of range');
 * }
 */
export function validatePCMSamples(samples: Float32Array): boolean {
  for (let i = 0; i < samples.length; i++) {
    const sample = samples[i];

    // Check if finite (not NaN or Infinity)
    if (!isFinite(sample)) {
      console.warn(`Invalid PCM sample at index ${i}: ${sample}`);
      return false;
    }

    // Check if in valid range (allow slight overshoot for headroom)
    if (sample < -1.5 || sample > 1.5) {
      console.warn(
        `PCM sample out of range at index ${i}: ${sample.toFixed(3)}`
      );
      return false;
    }
  }

  return true;
}

/**
 * Clip PCM samples to [-1.0, 1.0] range to prevent distortion
 *
 * Soft clipping (tanh-like) would be more musical, but hard clipping
 * is faster and acceptable for most audio.
 *
 * @param samples Float32Array to clip (modified in place)
 * @returns The same Float32Array for chaining
 *
 * @example
 * const pcm = new Float32Array([0.5, 1.2, -0.8]);
 * clipPCMSamples(pcm);
 * // pcm = [0.5, 1.0, -0.8]
 */
export function clipPCMSamples(samples: Float32Array): Float32Array {
  for (let i = 0; i < samples.length; i++) {
    if (samples[i] > 1.0) {
      samples[i] = 1.0;
    } else if (samples[i] < -1.0) {
      samples[i] = -1.0;
    }
  }
  return samples;
}

/**
 * Resample PCM data from one sample rate to another
 *
 * Uses linear interpolation for simplicity and speed.
 * For high-quality resampling, consider using a library like audioworklet-polyfill.
 *
 * @param samples Float32Array with samples at sourceSampleRate
 * @param sourceSampleRate Original sample rate (e.g., 48000)
 * @param targetSampleRate Target sample rate (e.g., 44100)
 * @returns Float32Array resampled to targetSampleRate
 *
 * @example
 * const pcm48k = new Float32Array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6]);
 * const pcm44k = resamplePCM(pcm48k, 48000, 44100);
 * // pcm44k has ~5.5 samples instead of 6
 */
export function resamplePCM(
  samples: Float32Array,
  sourceSampleRate: number,
  targetSampleRate: number
): Float32Array {
  if (sourceSampleRate === targetSampleRate) {
    return samples.slice(); // Return copy
  }

  // Calculate resampling ratio
  const ratio = targetSampleRate / sourceSampleRate;
  const targetLength = Math.ceil(samples.length * ratio);
  const resampled = new Float32Array(targetLength);

  for (let i = 0; i < targetLength; i++) {
    const sourceIndex = i / ratio;
    const sourceFloor = Math.floor(sourceIndex);
    const sourceCeil = Math.min(sourceFloor + 1, samples.length - 1);
    const fraction = sourceIndex - sourceFloor;

    // Linear interpolation
    resampled[i] =
      samples[sourceFloor] * (1 - fraction) +
      samples[sourceCeil] * fraction;
  }

  return resampled;
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
  crossfadeSamples: number;
}

/**
 * Decode a complete audio_chunk WebSocket message
 *
 * Combines base64 decoding with metadata extraction.
 *
 * @param message WebSocket message object with data and type
 * @returns Decoded PCM samples and metadata
 * @throws Error if message format is invalid
 *
 * @example
 * const message = {
 *   type: 'audio_chunk',
 *   data: {
 *     chunk_index: 0,
 *     samples: 'AQIDBA==',
 *     sample_count: 4,
 *     crossfade_samples: 1024
 *   }
 * };
 * const { samples, metadata } = decodeAudioChunkMessage(message, 48000, 2);
 */
export function decodeAudioChunkMessage(
  message: any,
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

  // Validate required fields
  if (!data.samples || typeof data.samples !== 'string') {
    throw new Error('Missing or invalid samples field in audio_chunk');
  }

  if (data.sample_count === undefined || data.sample_count <= 0) {
    throw new Error('Invalid sample_count in audio_chunk');
  }

  // Decode base64 PCM
  let samples: Float32Array;
  try {
    samples = decodePCMBase64(data.samples);
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
    crossfadeSamples: data.crossfade_samples ?? 0,
  };

  return { samples, metadata };
}

/**
 * Calculate sample count from duration and sample rate
 *
 * @param duration Duration in seconds
 * @param sampleRate Sample rate in Hz (e.g., 48000)
 * @returns Number of samples
 *
 * @example
 * const samples = durationToSampleCount(1.0, 48000); // 48000
 */
export function durationToSampleCount(
  duration: number,
  sampleRate: number
): number {
  return Math.ceil(duration * sampleRate);
}

/**
 * Calculate duration from sample count and sample rate
 *
 * @param sampleCount Number of samples
 * @param sampleRate Sample rate in Hz
 * @returns Duration in seconds
 *
 * @example
 * const duration = sampleCountToDuration(48000, 48000); // 1.0
 */
export function sampleCountToDuration(
  sampleCount: number,
  sampleRate: number
): number {
  return sampleCount / sampleRate;
}
