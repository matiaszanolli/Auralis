/**
 * Ring-buffer primitives and capacity sizing for PCMStreamBuffer.
 *
 * Split out of PCMStreamBuffer.ts (#5840): pure functions over a Float32Array
 * and two indices, with no state of their own.
 *
 * @copyright (C) 2024 Auralis Team
 * @license AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
 */

/** Ceiling: ~5 minutes @ 44.1kHz stereo. Long tracks cap here like before. */
export const MAX_CAPACITY_BYTES = 100 * 1024 * 1024;
/** Floor: ~2.7s @ 48kHz stereo, so tiny clips keep some headroom. */
export const MIN_CAPACITY_BYTES = 1024 * 1024;

/**
 * Size a buffer for a stream of the given length (#5663).
 *
 * 50% slack above the stream's own bytes keeps the percentage-based flow
 * control (75% pause / 50% resume of capacity) from pausing delivery for a
 * track that fits whole, and absorbs chunks still in flight around a
 * buffer_full; the 100MB cap and 1MB floor bound both ends. A 30s clip
 * allocates ~13MB instead of 100MB.
 */
export function capacityForStream(
  durationSeconds: number,
  sampleRate: number,
  channels: number
): number {
  const streamBytes = Math.max(durationSeconds, 0) * sampleRate * channels * 4;
  const withSlack = streamBytes + streamBytes / 2;
  return Math.min(
    MAX_CAPACITY_BYTES,
    Math.max(withSlack, MIN_CAPACITY_BYTES)
  );
}

/** Copy `count` samples out of the ring starting at `readPos`, wrapping at the end. */
export function readRing(buffer: Float32Array, readPos: number, count: number): Float32Array {
  const result = new Float32Array(count);
  const bufferCapacity = buffer.length;
  if (readPos + count <= bufferCapacity) {
    // Simple case: no wrap-around
    result.set(buffer.subarray(readPos, readPos + count));
  } else {
    // Wrap-around case
    const firstPart = bufferCapacity - readPos;
    result.set(buffer.subarray(readPos, bufferCapacity), 0);
    result.set(buffer.subarray(0, count - firstPart), firstPart);
  }
  return result;
}

/** Copy `pcm` into the ring starting at `writePos`, wrapping at the end. */
export function writeRing(buffer: Float32Array, writePos: number, pcm: Float32Array): void {
  const bufferCapacity = buffer.length;
  if (writePos + pcm.length <= bufferCapacity) {
    // Simple case: no wrap-around
    buffer.set(pcm, writePos);
  } else {
    // Wrap-around case
    const firstPart = bufferCapacity - writePos;
    buffer.set(pcm.subarray(0, firstPart), writePos);
    buffer.set(pcm.subarray(firstPart), 0);
  }
}
