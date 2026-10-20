/**
 * PCMStreamBuffer - Circular buffer for streaming PCM samples
 *
 * Provides efficient real-time PCM sample buffering with:
 * - Circular buffer design for memory efficiency
 * - Automatic wrap-around handling
 * - Buffer overflow/underflow detection
 *
 * @copyright (C) 2024 Auralis Team
 * @license AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
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
 * - Capacity sized from the stream's own length (see capacityForStream);
 *   the default constructor argument is only a legacy fallback
 * - Circular write/read pointers with wrap-around
 * - Thread-safe (single-threaded via event loop)
 *
 * No boundary crossfade (#4642): ChunkOperations.extract_chunk_segment trims
 * every processed chunk to its non-overlapping CHUNK_INTERVAL segment before
 * it reaches the streaming layer, so adjacent chunks share no samples and
 * there is nothing to blend. The server's apply_boundary_crossfade was made a
 * no-op for the same reason in #3514; the client-side linear-fade
 * implementation that used to live here was permanently unreachable and has
 * been removed along with the crossfade_samples wire field.
 */
export class PCMStreamBuffer {
  /** Ceiling: ~5 minutes @ 44.1kHz stereo. Long tracks cap here like before. */
  static readonly MAX_CAPACITY_BYTES = 100 * 1024 * 1024;
  /** Floor: ~2.7s @ 48kHz stereo, so tiny clips keep some headroom. */
  static readonly MIN_CAPACITY_BYTES = 1024 * 1024;

  private buffer: Float32Array | null = null;
  private writePos: number = 0;
  private readPos: number = 0;
  private sampleRate: number = 48000;
  private channels: number = 2;
  private capacity: number = 0;
  private isInitialized: boolean = false;

  // Statistics
  private totalAppended: number = 0;
  private totalRead: number = 0;

  /**
   * Create a new PCMStreamBuffer
   * @param capacity - Buffer capacity in bytes. Prefer sizing with
   *   capacityForStream() from the stream-start metadata; the 100MB default
   *   was a blanket cost on every stream regardless of its length (#5663).
   */
  constructor(capacity: number = PCMStreamBuffer.MAX_CAPACITY_BYTES) {
    this.capacity = capacity;
  }

  /**
   * Size a buffer for a stream of the given length (#5663).
   *
   * 50% slack above the stream's own bytes keeps the percentage-based flow
   * control (75% pause / 50% resume of capacity) from pausing delivery for a
   * track that fits whole, and absorbs chunks still in flight around a
   * buffer_full; the 100MB cap and 1MB floor bound both ends. A 30s clip
   * allocates ~13MB instead of 100MB.
   */
  static capacityForStream(
    durationSeconds: number,
    sampleRate: number,
    channels: number
  ): number {
    const streamBytes = Math.max(durationSeconds, 0) * sampleRate * channels * 4;
    const withSlack = streamBytes + streamBytes / 2;
    return Math.min(
      PCMStreamBuffer.MAX_CAPACITY_BYTES,
      Math.max(withSlack, PCMStreamBuffer.MIN_CAPACITY_BYTES)
    );
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

    this.totalAppended = 0;
    this.totalRead = 0;
  }

  /**
   * Append PCM samples to buffer
   * @param pcm - Float32Array of PCM samples
   */
  append(pcm: Float32Array): void {
    if (!this.isInitialized || !this.buffer) {
      throw new Error('PCMStreamBuffer not initialized. Call initialize() first.');
    }

    const requiredSpace = pcm.length;

    // Check for overflow
    const availableCapacity = this.capacity / 4;
    const usedSamples = this.getAvailableSamples();

    if (usedSamples + requiredSpace > availableCapacity) {
      // Log overflow warning - writeToBuffer will drop new data to preserve playback position
      console.warn(
        `[PCMStreamBuffer] Buffer near capacity: used=${usedSamples} (${(usedSamples / this.sampleRate / this.channels).toFixed(1)}s), ` +
        `adding=${requiredSpace}, capacity=${availableCapacity}. New data may be dropped.`
      );
    }

    // Write to circular buffer with wrap-around
    this.writeToBuffer(pcm);
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
   *
   * O(1): the read/write positions alone define the live range — nothing
   * ever reads outside [readPos, writePos), so zeroing the backing array was
   * a full-buffer memset on the main thread per seek for no observable
   * effect (#5663). Stale bytes are never exposed: appends overwrite them
   * before the positions make them readable again.
   */
  reset(): void {
    this.writePos = 0;
    this.readPos = 0;

    this.totalAppended = 0;
    this.totalRead = 0;
  }

  /**
   * Dispose buffer (release memory)
   */
  dispose(): void {
    this.buffer = null;
    this.isInitialized = false;
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

    // Calculate available space before write. Subtract the slot initialize()
    // reserved to disambiguate full from empty (#5477): without the -1, writes
    // totalling the backing length were accepted, landing writePos back on
    // readPos — a full buffer that getAvailableSamples() then reported as
    // empty, silently dropping everything.
    const bufferCapacity = this.buffer.length;
    const sampleCount = pcm.length;
    const currentlyUsed = this.getAvailableSamples();
    const freeSpace = bufferCapacity - currentlyUsed - 1;

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
