/**
 * PlaybackController - Playback state management and control logic
 *
 * Responsibility: Manage play/pause/seek operations and state transitions
 *
 * Extracted from UnifiedWebMAudioPlayer for:
 * - Clear separation of playback control logic
 * - Testable play/pause/seek strategies
 * - Independent state machine implementation
 *
 * Key Features:
 * - Play with automatic chunk loading and buffer management
 * - Pause with position tracking
 * - Seek with priority-based chunk preloading
 * - Resumable playback tracking
 * - State transition validation
 * - Adaptive timeout management for chunk loading
 */

import { AdaptiveTimeoutManager } from './AdaptiveTimeoutManager';

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

export type PlaybackState =
  | 'idle'
  | 'loading'
  | 'ready'
  | 'playing'
  | 'paused'
  | 'buffering'
  | 'seeking'
  | 'error';

type EventCallback = (data?: any) => void;

export class PlaybackController {
  private state: PlaybackState = 'idle';
  private pauseTime: number = 0; // Position when paused
  private currentChunkIndex: number = 0;
  private chunks: ChunkInfo[] = [];
  private metadata: StreamMetadata | null = null;

  private eventCallbacks = new Map<string, Set<EventCallback>>();
  private debug: (msg: string) => void = () => {};
  private timeoutManager: AdaptiveTimeoutManager;

  constructor(debugFn?: (msg: string) => void) {
    if (debugFn) {
      this.debug = debugFn;
    }
    this.timeoutManager = new AdaptiveTimeoutManager(debugFn);
  }

  /**
   * Initialize chunks array (called when track metadata loads)
   */
  initChunks(chunkCount: number): void {
    this.chunks = Array.from({ length: chunkCount }, () => ({
      isLoaded: false,
      isLoading: false,
      audioBuffer: null
    }));
    // Reset timeout manager for new track
    this.timeoutManager.reset();
    this.debug(`[PLAYBACK] Initialized ${chunkCount} chunks`);
  }

  /**
   * Set track metadata
   */
  setMetadata(metadata: StreamMetadata): void {
    this.metadata = metadata;
  }

  /**
   * Get current playback state
   */
  getState(): PlaybackState {
    return this.state;
  }

  /**
   * Set playback state with validation
   */
  setState(newState: PlaybackState): void {
    if (this.state === newState) return;
    this.debug(`[PLAYBACK] State: ${this.state} → ${newState}`);
    this.state = newState;
    this.emit('state-changed', { state: newState });
  }

  /**
   * Get current position in track
   */
  getCurrentPosition(): number {
    return this.pauseTime;
  }

  /**
   * Set current position (usually called by timing engine)
   */
  setCurrentPosition(time: number): void {
    this.pauseTime = Math.max(0, time);
  }

  /**
   * Get current chunk index
   */
  getCurrentChunkIndex(): number {
    return this.currentChunkIndex;
  }

  /**
   * Set current chunk index
   */
  setCurrentChunkIndex(chunkIndex: number): void {
    this.currentChunkIndex = chunkIndex;
  }

  /**
   * Play from current position or specific time
   *
   * Performs these steps:
   * 1. Calculate which chunk to start from
   * 2. Ensure that chunk is loaded
   * 3. Determine offset within chunk
   * 4. Emit play-request for orchestrator to handle
   *
   * @returns Promise that resolves when playback can start
   */
  async play(): Promise<void> {
    if (!this.metadata) {
      throw new Error('No track loaded');
    }

    this.setState('playing');

    // Calculate chunk to play based on current position
    const currentTime = this.pauseTime || 0;
    const chunkInterval = this.metadata.chunk_interval || this.metadata.chunk_duration || 10;
    const chunkDuration = this.metadata.chunk_duration || 10;

    // Calculate which chunk contains this time
    const chunkIndex = Math.floor(currentTime / chunkInterval);

    // Calculate offset within chunk
    const chunkStartTime = chunkIndex * chunkInterval;
    const offsetInChunk = currentTime - chunkStartTime;

    this.debug(`[PLAYBACK] Play from ${currentTime.toFixed(2)}s (chunk ${chunkIndex}, offset ${offsetInChunk.toFixed(2)}s)`);

    // Request orchestrator to load and play chunk
    this.emit('play-requested', {
      chunkIndex,
      offsetInChunk,
      chunkInterval,
      chunkDuration
    });

    // Wait for chunk to be ready with adaptive timeout
    const maxWaitTime = this.timeoutManager.getTimeoutMs();
    const startTime = Date.now();
    while (!this.chunks[chunkIndex]?.isLoaded && Date.now() - startTime < maxWaitTime) {
      await new Promise(resolve => setTimeout(resolve, 50));
    }

    // Record load time for adaptive timeout tuning
    const loadTimeMs = Date.now() - startTime;
    this.timeoutManager.recordChunkLoad(chunkIndex, loadTimeMs);

    if (!this.chunks[chunkIndex]?.isLoaded) {
      throw new Error(
        `Chunk ${chunkIndex} failed to load within adaptive timeout ` +
        `(${this.timeoutManager.getTimeoutSeconds().toFixed(1)}s)`
      );
    }
  }

  /**
   * Pause playback
   * Saves current position for resume
   */
  pause(): void {
    if (this.state !== 'playing') return;

    this.debug(`[PLAYBACK] Pause at ${this.pauseTime.toFixed(2)}s`);
    this.setState('paused');

    // Emit pause request so orchestrator can stop audio
    this.emit('pause-requested', { pauseTime: this.pauseTime });
  }

  /**
   * Seek to specific time
   *
   * Performs these steps:
   * 1. Calculate target chunk and offset
   * 2. Queue target chunk with high priority
   * 3. Queue adjacent chunks for smoother playback
   * 4. Wait for target chunk to load
   * 5. Resume playback if was playing
   *
   * @param time - Target time in seconds
   * @returns Promise that resolves when seek completes
   */
  async seek(time: number): Promise<void> {
    if (!this.metadata) {
      throw new Error('No track loaded');
    }

    const wasPlaying = this.state === 'playing';
    const chunkInterval = this.metadata.chunk_interval || this.metadata.chunk_duration || 10;

    // Calculate target chunk
    const targetChunk = Math.floor(time / chunkInterval);
    const chunkStartTime = targetChunk * chunkInterval;
    const offset = time - chunkStartTime;

    this.debug(`[PLAYBACK] Seek to ${time.toFixed(2)}s (chunk ${targetChunk}, offset ${offset.toFixed(2)}s)`);

    // Update position
    this.pauseTime = time;

    // Request orchestrator to handle seeking
    // Include adjacent chunks for preloading
    this.emit('seek-requested', {
      targetTime: time,
      targetChunk,
      offset,
      chunkInterval,
      wasPlaying,
      adjacentChunks: {
        prev: targetChunk > 0 ? targetChunk - 1 : null,
        next: targetChunk + 1 < this.chunks.length ? targetChunk + 1 : null
      }
    });

    // Wait for target chunk to be loaded with adaptive timeout
    const maxWaitTime = this.timeoutManager.getTimeoutMs();
    const startTime = Date.now();
    while (!this.chunks[targetChunk]?.isLoaded && Date.now() - startTime < maxWaitTime) {
      await new Promise(resolve => setTimeout(resolve, 50));
    }

    // Record load time for adaptive timeout tuning
    const loadTimeMs = Date.now() - startTime;
    this.timeoutManager.recordChunkLoad(targetChunk, loadTimeMs);

    if (!this.chunks[targetChunk]?.isLoaded) {
      throw new Error(
        `Chunk ${targetChunk} failed to load within adaptive seek timeout ` +
        `(${this.timeoutManager.getTimeoutSeconds().toFixed(1)}s)`
      );
    }
  }

  /**
   * Get chunk info
   */
  getChunk(chunkIndex: number): ChunkInfo | null {
    if (chunkIndex >= this.chunks.length) return null;
    return this.chunks[chunkIndex];
  }

  /**
   * Get total chunks
   */
  getChunkCount(): number {
    return this.chunks.length;
  }

  /**
   * Update chunk loading state (called by ChunkPreloadManager)
   */
  updateChunkLoadState(chunkIndex: number, isLoading: boolean, isLoaded: boolean): void {
    if (chunkIndex < this.chunks.length) {
      this.chunks[chunkIndex].isLoading = isLoading;
      this.chunks[chunkIndex].isLoaded = isLoaded;
    }
  }

  /**
   * Update chunk audio buffer (called by ChunkPreloadManager)
   */
  setChunkAudioBuffer(chunkIndex: number, audioBuffer: AudioBuffer | null): void {
    if (chunkIndex < this.chunks.length) {
      this.chunks[chunkIndex].audioBuffer = audioBuffer;
    }
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
        console.error(`[PlaybackController] Error in ${event} callback:`, error);
      }
    });
  }

  /**
   * Clean up resources
   */
  destroy(): void {
    this.chunks = [];
    this.metadata = null;
    this.eventCallbacks.clear();
  }
}
