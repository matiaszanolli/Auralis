/**
 * AudioContextController - Web Audio API management and chunk playback
 *
 * Responsibility: Create/manage AudioContext, schedule chunk playback, handle crossfading
 *
 * Extracted from UnifiedWebMAudioPlayer for:
 * - Clear separation of audio API concern
 * - Testable playback logic
 * - Independent audio scheduling strategy
 *
 * Key Features:
 * - Lazy AudioContext creation (on first user gesture)
 * - Gain node management for volume control
 * - Chunk scheduling with automatic crossfading
 * - Precise timing mapping for progress bar accuracy
 * - End-of-playback detection and chunk chaining
 */

export interface ChunkInfo {
  isLoaded: boolean;
  isLoading: boolean;
  audioBuffer: AudioBuffer | null;
}

export interface StreamMetadata {
  duration: number;
  chunk_duration: number;
  chunk_interval: number;
}

type EventCallback = (data?: any) => void;

export class AudioContextController {
  private audioContext: AudioContext | null = null;
  private currentSource: AudioBufferSource | null = null;
  private gainNode: GainNode | null = null;
  private volume: number = 1.0;

  // Timing mapping (single source of truth for timeline)
  private audioContextStartTime: number = 0;
  private trackStartTime: number = 0;

  // Configuration
  private chunkDuration: number = 10; // Default chunk duration in seconds
  private chunkInterval: number = 10; // Default interval between chunk starts

  private eventCallbacks = new Map<string, Set<EventCallback>>();
  private debug: (msg: string) => void = () => {};

  constructor(
    chunkDuration: number = 10,
    chunkInterval: number = 10,
    debugFn?: (msg: string) => void
  ) {
    this.chunkDuration = chunkDuration;
    this.chunkInterval = chunkInterval;
    if (debugFn) {
      this.debug = debugFn;
    }
  }

  /**
   * Ensure AudioContext exists and is properly initialized
   * Required by browser autoplay policy - must be called on user gesture
   */
  ensureAudioContext(): AudioContext {
    if (!this.audioContext) {
      try {
        const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
        if (!AudioContextClass) {
          throw new Error('Web Audio API not supported in this browser');
        }
        this.audioContext = new AudioContextClass();
        this.gainNode = this.audioContext.createGain();
        this.gainNode.connect(this.audioContext.destination);
        this.debug(`AudioContext created on first user gesture, state: ${this.audioContext.state}`);
      } catch (error: any) {
        this.debug(`ERROR: Failed to create AudioContext: ${error.message}`);
        throw error;
      }
    }
    return this.audioContext;
  }

  /**
   * Resume AudioContext if suspended (browser autoplay policy)
   */
  async resumeAudioContext(): Promise<void> {
    if (!this.audioContext) {
      this.debug('No AudioContext to resume');
      return;
    }

    try {
      const state = this.audioContext.state;
      this.debug(`AudioContext state before resume: ${state}`);

      if (state === 'suspended') {
        this.debug('AudioContext suspended, resuming...');
        await this.audioContext.resume();
        this.debug(`AudioContext resumed successfully, state: ${this.audioContext.state}`);
      } else {
        this.debug(`AudioContext already ${state}, no resume needed`);
      }
    } catch (error: any) {
      this.debug(`ERROR: Failed to resume AudioContext: ${error.message}`);
      throw error;
    }
  }

  /**
   * Set volume (0-1)
   */
  setVolume(volume: number): void {
    this.volume = Math.max(0, Math.min(1, volume));
    if (this.gainNode) {
      this.gainNode.gain.value = this.volume;
    }
  }

  /**
   * Get current volume
   */
  getVolume(): number {
    return this.volume;
  }

  /**
   * Get audio context instance
   */
  getAudioContext(): AudioContext | null {
    return this.audioContext;
  }

  /**
   * Update chunk timing (called when loading track metadata)
   */
  updateChunkTiming(chunkDuration: number, chunkInterval: number): void {
    this.chunkDuration = chunkDuration;
    this.chunkInterval = chunkInterval;
    this.debug(`Updated chunk timing: duration=${chunkDuration}s, interval=${chunkInterval}s`);
  }

  /**
   * Play a chunk with precise timing and automatic crossfading
   *
   * This is the core playback method that:
   * 1. Stops previous source
   * 2. Creates new buffer source
   * 3. Updates timing reference for progress bar
   * 4. Schedules next chunk for crossfading
   * 5. Handles end-of-playback
   *
   * @param chunkIndex - Index of chunk to play
   * @param audioBuffer - Decoded audio buffer
   * @param offset - Seek offset within chunk (seconds)
   * @param isPlaying - Current playback state
   * @param totalChunks - Total chunks in track
   * @param metadata - Track metadata (duration, chunk info)
   * @returns Promise that resolves when chunk finishes playing
   */
  async playChunk(
    chunkIndex: number,
    audioBuffer: AudioBuffer,
    offset: number = 0,
    isPlaying: boolean = true,
    totalChunks: number = 0,
    metadata?: StreamMetadata
  ): Promise<void> {
    if (!this.audioContext) {
      throw new Error('AudioContext not initialized');
    }

    if (!audioBuffer || !audioBuffer.duration) {
      throw new Error(`Chunk ${chunkIndex} has invalid audio buffer: ${!audioBuffer ? 'null' : 'undefined duration'}`);
    }

    // Stop previous source
    if (this.currentSource) {
      try {
        this.currentSource.stop();
        this.currentSource.disconnect();
      } catch (e) {
        // Ignore errors stopping already-stopped sources
      }
    }

    // Create gain node for this chunk (volume control)
    const chunkGainNode = this.audioContext.createGain();
    chunkGainNode.connect(this.gainNode!);
    chunkGainNode.gain.value = this.volume;

    // Create buffer source for this chunk
    const source = this.audioContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(chunkGainNode);

    // Update timing reference (only on initial play or seek, not on chunk transitions)
    const chunkStartsSeamlessly = isPlaying && offset === 0 && chunkIndex === this.getLastPlayedChunkIndex();
    if (!chunkStartsSeamlessly) {
      // Initial play or seek: record timing origin
      this.audioContextStartTime = this.audioContext.currentTime;
      this.trackStartTime = chunkIndex * this.chunkInterval + offset;
      this.debug(
        `[TIME_MAP] Set origin: audioCtx=${this.audioContextStartTime.toFixed(3)}s → ` +
        `track=${this.trackStartTime.toFixed(3)}s`
      );
    } else {
      // Chunk transition: timing reference stays same
      this.debug(`[TIME_MAP] Chunk transition (${chunkIndex}): mapping unchanged`);
    }

    // Calculate play duration
    const actualBufferDuration = audioBuffer.duration;
    const isLastChunk = chunkIndex + 1 >= totalChunks;
    const chunkStartTime = chunkIndex * this.chunkInterval;
    const overlapDuration = this.chunkDuration - this.chunkInterval; // Overlap with next chunk

    let bufferOffset = offset;
    let playDuration: number;

    if (offset > 0) {
      // Seeking within chunk
      playDuration = Math.max(0, actualBufferDuration - bufferOffset);
    } else if (isLastChunk) {
      // Last chunk - only play until track end
      const remainingTrack = Math.max(0, (metadata?.duration || actualBufferDuration) - chunkStartTime);
      playDuration = Math.min(actualBufferDuration, remainingTrack);
    } else {
      // Normal chunk - play full duration for crossfading
      playDuration = Math.min(actualBufferDuration, this.chunkDuration);
    }

    // Safety: never exceed buffer
    playDuration = Math.min(playDuration, actualBufferDuration - bufferOffset);

    if (playDuration <= 0) {
      this.debug(
        `WARNING: Chunk ${chunkIndex} invalid duration ` +
        `(buffer=${actualBufferDuration.toFixed(2)}s, offset=${bufferOffset.toFixed(2)}s)`
      );
      playDuration = 0.1;
    }

    // Debug logging for first few chunks
    if (chunkIndex < 5) {
      this.debug(
        `[TIMING] Chunk ${chunkIndex}: buffer=${actualBufferDuration.toFixed(2)}s, ` +
        `offset=${bufferOffset.toFixed(2)}s, duration=${playDuration.toFixed(2)}s, ` +
        `overlap=${overlapDuration.toFixed(2)}s`
      );
    }

    // Validate audioBuffer is still available before playback
    if (!audioBuffer || !audioBuffer.duration) {
      throw new Error(`Invalid audio buffer for chunk ${chunkIndex}: duration is undefined`);
    }

    // Start playback
    source.start(0, bufferOffset, playDuration);
    this.currentSource = source;

    // Set up next chunk scheduling for crossfading
    let nextChunkScheduled = false;
    let fadeTimeoutId: number | null = null;

    if (!isLastChunk && offset === 0) {
      // Schedule next chunk during overlap period for crossfading
      const fadeStartTime = Math.max(0, playDuration - overlapDuration);

      if (fadeStartTime > 0) {
        const scheduleNextChunk = () => {
          if (isPlaying && this.currentSource === source && !nextChunkScheduled) {
            nextChunkScheduled = true;
            try {
              this.debug(`[FADE] Starting next chunk (${chunkIndex + 1}) for crossfading`);
              this.emit('schedule-next-chunk', { chunkIndex: chunkIndex + 1 });
            } catch (error: any) {
              this.debug(`Error scheduling next chunk: ${error.message}`);
            }
          }
        };

        const delayMs = fadeStartTime * 1000;
        this.debug(
          `Scheduling next chunk (${chunkIndex + 1}) to start in ` +
          `${delayMs.toFixed(0)}ms for crossfading`
        );

        fadeTimeoutId = window.setTimeout(scheduleNextChunk, delayMs);
      }
    }

    // Handle end of playback
    return new Promise((resolve) => {
      source.onended = () => {
        try {
          source.disconnect();
          chunkGainNode.disconnect();

          if (fadeTimeoutId !== null) {
            clearTimeout(fadeTimeoutId);
          }

          if (!isLastChunk && isPlaying && !nextChunkScheduled) {
            // Next chunk should play now
            this.emit('play-next-chunk', { chunkIndex: chunkIndex + 1 });
          } else if (isLastChunk && isPlaying) {
            // Track finished
            this.emit('track-ended', {});
          }
        } catch (error: any) {
          this.debug(`Error in chunk end handler: ${error.message}`);
        }
        resolve();
      };
    });
  }

  /**
   * Stop current playback and clean up
   */
  stopCurrentSource(): void {
    if (this.currentSource) {
      try {
        this.currentSource.stop();
        this.currentSource.disconnect();
      } catch (e) {
        // Ignore errors on already-stopped sources
      }
      this.currentSource = null;
    }
  }

  /**
   * Check if currently playing
   */
  getIsPlaying(): boolean {
    return this.currentSource !== null;
  }

  /**
   * Get last played chunk index (for seamless transitions)
   */
  private getLastPlayedChunkIndex(): number {
    // This is a placeholder - would be set by controller
    return -1;
  }

  /**
   * Get current time reference for progress bar
   * Uses audioContext.currentTime as the source of truth
   */
  getCurrentTimeReference(): { audioCtxStartTime: number; trackStartTime: number } {
    return {
      audioCtxStartTime: this.audioContextStartTime,
      trackStartTime: this.trackStartTime
    };
  }

  /**
   * Set time reference (called when seeking or loading)
   */
  setTimeReference(audioCtxTime: number, trackTime: number): void {
    this.audioContextStartTime = audioCtxTime;
    this.trackStartTime = trackTime;
  }

  /**
   * Event system: Subscribe to events
   */
  on(event: string, callback: EventCallback): void {
    if (!this.eventCallbacks.has(event)) {
      this.eventCallbacks.set(event, new Set());
    }
    this.eventCallbacks.get(event)!.add(callback);
  }

  /**
   * Event system: Unsubscribe from events
   */
  off(event: string, callback: EventCallback): void {
    this.eventCallbacks.get(event)?.delete(callback);
  }

  /**
   * Event system: Emit event
   */
  private emit(event: string, data?: any): void {
    this.eventCallbacks.get(event)?.forEach(callback => {
      try {
        callback(data);
      } catch (error) {
        console.error(`[AudioContextController] Error in ${event} callback:`, error);
      }
    });
  }

  /**
   * Clean up resources
   */
  destroy(): void {
    this.stopCurrentSource();
    this.eventCallbacks.clear();
    if (this.audioContext) {
      this.audioContext.close().catch(() => {
        // Ignore errors closing context
      });
      this.audioContext = null;
    }
  }
}
