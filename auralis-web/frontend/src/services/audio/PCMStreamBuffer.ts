/**
 * PCMStreamBuffer - Circular buffer for streaming PCM samples
 *
 * Provides efficient real-time PCM sample buffering with:
 * - Circular buffer design for memory efficiency
 * - Automatic wrap-around handling
 * - Crossfade blending at chunk boundaries
 * - Buffer overflow/underflow detection
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

export interface BufferMetadata {
  sampleRate: number;
  channels: number;
  capacity: number;
  availableSamples: number;
  isFull: boolean;
  isEmpty: boolean;
  totalAppended: number;
  totalRead: number;
}

/**
 * PCMStreamBuffer - Circular buffer for streaming audio
 *
 * Design:
 * - Default 5MB capacity (~6 seconds at 48kHz stereo)
 * - Circular write/read pointers with wrap-around
 * - Automatic crossfading when appending chunks
 * - Thread-safe (single-threaded via event loop)
 */
export class PCMStreamBuffer {
  private buffer: Float32Array | null = null;
  private writePos: number = 0;
  private readPos: number = 0;
  private sampleRate: number = 48000;
  private channels: number = 2;
  private capacity: number = 0;
  private isInitialized: boolean = false;

  // Crossfade state
  private lastChunkEnd: Float32Array | null = null;
  private crossfadeLength: number = 0;

  // Statistics
  private totalAppended: number = 0;
  private totalRead: number = 0;

  /**
   * Create a new PCMStreamBuffer
   * @param capacity - Buffer capacity in bytes (default 100MB for ~5 minutes @ 44.1kHz stereo)
   *
   * Calculation: 44100 Hz × 2 channels × 4 bytes × 300 seconds = ~105MB
   * We use 100MB to safely buffer most tracks without overflow.
   * This prevents the audio position jumping issue caused by discarding unplayed audio.
   */
  constructor(capacity: number = 100 * 1024 * 1024) {
    this.capacity = capacity;
  }

  /**
   * Initialize buffer with audio parameters
   * @param sampleRate - Sample rate in Hz
   * @param channels - Number of channels
   * @param capacityBytes - Optional buffer capacity in bytes (overrides constructor capacity)
   */
  initialize(sampleRate: number, channels: number, capacityBytes?: number): void {
    this.sampleRate = sampleRate;
    this.channels = channels;

    // Allow overriding capacity at initialization time
    if (capacityBytes !== undefined) {
      this.capacity = capacityBytes;
    }

    // Capacity in samples = bytes / (4 bytes per float32 sample)
    // Reserve one slot to distinguish between full and empty states
    const capacityInSamples = this.capacity / 4;
    this.buffer = new Float32Array(capacityInSamples + 1);

    this.writePos = 0;
    this.readPos = 0;
    this.isInitialized = true;
    this.lastChunkEnd = null;
    this.crossfadeLength = 0;
    this.totalAppended = 0;
    this.totalRead = 0;
  }

  /**
   * Append PCM samples to buffer with optional crossfading
   * @param pcm - Float32Array of PCM samples
   * @param crossfadeSamples - Number of samples to crossfade (0 = no crossfade)
   */
  append(pcm: Float32Array, crossfadeSamples: number = 0): void {
    if (!this.isInitialized || !this.buffer) {
      throw new Error('PCMStreamBuffer not initialized. Call initialize() first.');
    }

    const sampleCount = pcm.length;

    // Check for overflow
    const availableCapacity = this.capacity / 4;
    const usedSamples = this.getAvailableSamples();
    const requiredSpace = sampleCount + crossfadeSamples;

    if (usedSamples + requiredSpace > availableCapacity) {
      // Log overflow warning - writeToBuffer will drop new data to preserve playback position
      console.warn(
        `[PCMStreamBuffer] Buffer near capacity: used=${usedSamples} (${(usedSamples / this.sampleRate / this.channels).toFixed(1)}s), ` +
        `adding=${requiredSpace}, capacity=${availableCapacity}. New data may be dropped.`
      );
    }

    // Apply crossfading if specified
    let dataToWrite = pcm;
    if (crossfadeSamples > 0 && this.lastChunkEnd !== null) {
      dataToWrite = this.applyCrossfade(pcm, crossfadeSamples);
    }

    // Write to circular buffer with wrap-around
    this.writeToBuffer(dataToWrite);

    // Save end of chunk for next crossfade
    if (crossfadeSamples > 0) {
      const endStart = Math.max(0, pcm.length - crossfadeSamples);
      this.lastChunkEnd = new Float32Array(pcm.slice(endStart));
    }
  }

  /**
   * Read samples from buffer
   * @param sampleCount - Number of samples to read
   * @returns Float32Array of samples (may be shorter if buffer doesn't have enough)
   */
  read(sampleCount: number): Float32Array {
    if (!this.isInitialized || !this.buffer) {
      throw new Error('PCMStreamBuffer not initialized. Call initialize() first.');
    }

    const availableSamples = this.getAvailableSamples();
    const toRead = Math.min(sampleCount, availableSamples);

    if (toRead === 0) {
      return new Float32Array(0);
    }

    const result = new Float32Array(toRead);
    const bufferCapacity = this.buffer.length;

    // Handle wrap-around case
    if (this.readPos + toRead <= bufferCapacity) {
      // Simple case: no wrap-around
      result.set(this.buffer.subarray(this.readPos, this.readPos + toRead));
    } else {
      // Wrap-around case
      const firstPart = bufferCapacity - this.readPos;
      result.set(this.buffer.subarray(this.readPos, bufferCapacity), 0);
      result.set(this.buffer.subarray(0, toRead - firstPart), firstPart);
    }

    // Advance read position
    this.readPos = (this.readPos + toRead) % bufferCapacity;
    this.totalRead += toRead;

    return result;
  }

  /**
   * Get number of available samples to read
   */
  getAvailableSamples(): number {
    if (!this.isInitialized) {
      return 0;
    }

    const bufferCapacity = this.buffer!.length;
    if (this.writePos >= this.readPos) {
      return this.writePos - this.readPos;
    } else {
      return bufferCapacity - this.readPos + this.writePos;
    }
  }

  /**
   * Check if buffer is full (no space for more samples)
   */
  isFull(): boolean {
    if (!this.isInitialized) {
      return false;
    }
    return this.getAvailableSamples() >= this.buffer!.length * 0.95;
  }

  /**
   * Check if buffer is empty
   */
  isEmpty(): boolean {
    return this.getAvailableSamples() === 0;
  }

  /**
   * Get buffer metadata for diagnostics
   */
  getMetadata(): BufferMetadata {
    return {
      sampleRate: this.sampleRate,
      channels: this.channels,
      capacity: this.capacity,
      availableSamples: this.getAvailableSamples(),
      isFull: this.isFull(),
      isEmpty: this.isEmpty(),
      totalAppended: this.totalAppended,
      totalRead: this.totalRead
    };
  }

  /**
   * Reset buffer (clear all samples)
   */
  reset(): void {
    this.writePos = 0;
    this.readPos = 0;
    this.lastChunkEnd = null;
    this.crossfadeLength = 0;
    this.totalAppended = 0;
    this.totalRead = 0;

    if (this.buffer) {
      this.buffer.fill(0);
    }
  }

  /**
   * Dispose buffer (release memory)
   */
  dispose(): void {
    this.buffer = null;
    this.isInitialized = false;
    this.lastChunkEnd = null;
  }

  /**
   * Apply crossfade between chunks
   * Blends the overlap region with linear fade
   */
  private applyCrossfade(currentChunk: Float32Array, crossfadeSamples: number): Float32Array {
    if (!this.lastChunkEnd || this.lastChunkEnd.length === 0) {
      return currentChunk;
    }

    const overlap = Math.min(crossfadeSamples, this.lastChunkEnd.length, currentChunk.length);
    if (overlap === 0) {
      return currentChunk;
    }

    // Create a copy to avoid modifying input
    const blended = new Float32Array(currentChunk);

    // Linear fade: fade in current chunk, fade out previous chunk
    for (let i = 0; i < overlap; i++) {
      const fadeProgress = i / overlap;
      const prevWeight = 1.0 - fadeProgress;
      const currWeight = fadeProgress;

      // Blend first `overlap` samples of current chunk with last `overlap` samples of previous chunk
      const prevSample = this.lastChunkEnd[this.lastChunkEnd.length - overlap + i] || 0;
      blended[i] = prevSample * prevWeight + blended[i] * currWeight;
    }

    return blended;
  }

  /**
   * Write samples to circular buffer
   *
   * IMPORTANT: If buffer is full, we DROP the new data instead of discarding
   * unplayed audio. This prevents audio position jumps - it's better to
   * potentially lose audio at the end of a long track than to have playback
   * jump to a random position mid-track.
   *
   * With the 100MB buffer (~5 minutes), overflow should be rare.
   */
  private writeToBuffer(pcm: Float32Array): void {
    if (!this.buffer) {
      return;
    }

    const bufferCapacity = this.buffer.length;
    const sampleCount = pcm.length;

    // Calculate available space before write
    const currentlyUsed = this.getAvailableSamples();
    const freeSpace = bufferCapacity - currentlyUsed;

    // Check if write would overflow
    if (sampleCount > freeSpace) {
      // DROP the new data instead of discarding unplayed audio
      // This prevents audio position jumps
      console.warn(
        `[PCMStreamBuffer] Buffer full! Dropping ${sampleCount} new samples ` +
        `(${(sampleCount / this.sampleRate / this.channels).toFixed(2)}s). ` +
        `Buffer: ${(currentlyUsed / this.sampleRate / this.channels).toFixed(1)}s used, ` +
        `${(freeSpace / this.sampleRate / this.channels).toFixed(1)}s free.`
      );
      // Don't write anything - preserve playback position integrity
      return;
    }

    // Handle wrap-around
    if (this.writePos + sampleCount <= bufferCapacity) {
      // Simple case: no wrap-around
      this.buffer.set(pcm, this.writePos);
    } else {
      // Wrap-around case
      const firstPart = bufferCapacity - this.writePos;
      this.buffer.set(pcm.subarray(0, firstPart), this.writePos);
      this.buffer.set(pcm.subarray(firstPart), 0);
    }

    // Advance write position
    this.writePos = (this.writePos + sampleCount) % bufferCapacity;
    this.totalAppended += sampleCount;
  }

  /**
   * Get current buffer fill percentage (for diagnostics)
   */
  getFillPercentage(): number {
    const available = this.getAvailableSamples();
    // Use logical capacity (bytes / 4), not actual buffer length (+1 for full/empty distinction)
    const logicalCapacity = this.capacity / 4;
    return (available / logicalCapacity) * 100;
  }
}

export default PCMStreamBuffer;
