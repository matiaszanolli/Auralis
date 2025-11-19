/**
 * UnifiedWebMAudioPlayer - Facade Orchestrator (Phase 3.6)
 * ===========================================================
 *
 * ARCHITECTURE (Phase 3.6):
 * - Thin facade that delegates to extracted services
 * - Services: TimingEngine, ChunkPreloadManager, AudioContextController, PlaybackController
 * - Public API unchanged for backward compatibility
 * - All logic delegated to focused, testable services
 *
 * Service Decomposition:
 * 1. TimingEngine - Playback timing and progress bar updates (50ms interval fix)
 * 2. ChunkPreloadManager - Chunk loading with priority queue
 * 3. AudioContextController - Web Audio API and playback
 * 4. PlaybackController - State machine and chunk sequencing
 * 5. MultiTierWebMBuffer - Audio buffer caching
 * 6. ChunkLoadPriorityQueue - Priority-based chunk loading
 *
 * @copyright (C) 2025 Auralis Team
 * @license GPLv3
 */

// Import services
import { TimingEngine } from './player/TimingEngine';
import { ChunkPreloadManager } from './player/ChunkPreloadManager';
import { AudioContextController } from './player/AudioContextController';
import { PlaybackController } from './player/PlaybackController';
import { MultiTierWebMBuffer } from './player/MultiTierWebMBuffer';
import { ChunkLoadPriorityQueue } from './player/ChunkLoadPriorityQueue';

export interface UnifiedWebMAudioPlayerConfig {
  /** Backend API base URL */
  apiBaseUrl?: string;

  /** Chunk duration (seconds, must match backend) */
  chunkDuration?: number;

  /** Enable audio enhancement (for cache key only, processing happens backend-side) */
  enhanced?: boolean;

  /** Enhancement preset (for cache key) */
  preset?: string;

  /** Enhancement intensity (for cache key) */
  intensity?: number;

  /** Number of chunks to preload */
  preloadChunks?: number;

  /** Enable debug logging */
  debug?: boolean;
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

export interface StreamMetadata {
  track_id: number;
  duration: number;
  total_chunks: number;
  chunk_duration: number;  // Actual chunk length in seconds (e.g., 15s)
  chunk_interval: number;  // Interval between chunk starts in seconds (e.g., 10s)
  mime_type: string;  // "audio/webm"
  codecs: string;  // "opus"
  format_version: string;  // "unified-v1.0"
}

export interface ChunkInfo {
  index: number;
  startTime: number;
  endTime: number;
  audioBuffer: AudioBuffer | null;
  isLoading: boolean;
  isLoaded: boolean;
}

type EventCallback = (data?: any) => void;

/**
 * UnifiedWebMAudioPlayer - Facade Orchestrator
 *
 * Thin facade that coordinates extracted services for playback.
 * Maintains backward-compatible public API while delegating all
 * logic to focused, independently testable services.
 *
 * Phase 3.6 Refactoring: Facade Pattern Implementation
 */
export class UnifiedWebMAudioPlayer {
  private config: Required<UnifiedWebMAudioPlayerConfig>;

  // Injected services
  private timingEngine: TimingEngine;
  private chunkPreloader: ChunkPreloadManager;
  private audioController: AudioContextController;
  private playbackController: PlaybackController;
  private buffer: MultiTierWebMBuffer;
  private loadQueue: ChunkLoadPriorityQueue;

  // Track state
  private trackId: number | null = null;
  private metadata: StreamMetadata | null = null;
  private chunks: ChunkInfo[] = [];

  // Playback state
  private state: PlaybackState = 'idle';
  private volume: number = 1.0;

  // Error tracking and user feedback
  private errorState: {
    lastError: Error | null;
    errorType: 'network' | 'decode' | 'timeout' | 'audiocontext' | 'unknown';
    failedChunks: Set<number>;
    errorCount: number;
    lastErrorTime: number;
  } = {
    lastError: null,
    errorType: 'unknown',
    failedChunks: new Set(),
    errorCount: 0,
    lastErrorTime: 0
  };

  // Event system
  private listeners: Map<string, Set<EventCallback>> = new Map();

  constructor(config: UnifiedWebMAudioPlayerConfig = {}) {
    this.config = {
      apiBaseUrl: config.apiBaseUrl || 'http://localhost:8765',
      chunkDuration: config.chunkDuration || 10,
      enhanced: config.enhanced !== undefined ? config.enhanced : true,
      preset: config.preset || 'adaptive',
      intensity: config.intensity !== undefined ? config.intensity : 1.0,
      preloadChunks: config.preloadChunks || 2,
      debug: config.debug || false
    };

    // Initialize services in dependency order
    // 1. Buffer and queue (no dependencies)
    this.buffer = new MultiTierWebMBuffer();
    this.loadQueue = new ChunkLoadPriorityQueue();

    // 2. Independent services
    this.timingEngine = new TimingEngine(null, this.debug.bind(this));
    this.audioController = new AudioContextController(
      this.config.chunkDuration,
      this.config.chunkDuration,
      this.debug.bind(this)
    );
    this.playbackController = new PlaybackController(this.debug.bind(this));

    // 3. Services with dependencies
    this.chunkPreloader = new ChunkPreloadManager(
      this.buffer,
      this.loadQueue,
      {
        apiBaseUrl: this.config.apiBaseUrl,
        trackId: 0, // Will be set on loadTrack
        enhanced: this.config.enhanced,
        preset: this.config.preset,
        intensity: this.config.intensity,
        preloadChunks: this.config.preloadChunks
      },
      null, // audioContext set later
      this.debug.bind(this)
    );

    // Wire service events
    this.wireServiceEvents();

    this.debug('UnifiedWebMAudioPlayer initialized (Phase 3.6 facade)');
  }

  /**
   * Wire service events to facade orchestration and external listeners
   */
  private wireServiceEvents(): void {
    // TimingEngine events → forward to listeners
    this.timingEngine.on('timeupdate', (e) => {
      this.emit('timeupdate', e);
    });

    // AudioContextController events → orchestration
    this.audioController.on('schedule-next-chunk', async (e) => {
      this.debug(`AudioController: schedule-next-chunk ${e.chunkIndex}`);
      await this.playChunkInternal(e.chunkIndex, 0).catch(err => {
        this.debug(`Error playing scheduled chunk: ${err.message}`);
        this.emit('error', err);
      });
    });

    this.audioController.on('play-next-chunk', async (e) => {
      this.debug(`AudioController: play-next-chunk ${e.chunkIndex}`);
      await this.playChunkInternal(e.chunkIndex, 0).catch(err => {
        this.debug(`Error playing next chunk: ${err.message}`);
      });
    });

    this.audioController.on('track-ended', () => {
      this.debug('AudioController: track ended');
      this.playbackController.setState('idle');
      this.state = 'idle';
      this.emit('ended');
    });

    // PlaybackController events
    this.playbackController.on('state-changed', (e) => {
      this.debug(`PlaybackController: state change ${this.state} → ${e.state}`);
      this.state = e.state;
      this.emit('statechange', { oldState: this.state, newState: e.state });
    });

    // Wire ChunkPreloadManager events
    this.wireChunkPreloaderEvents();
  }

  /**
   * Wire ChunkPreloadManager events (can be re-wired when preloader is recreated)
   */
  private wireChunkPreloaderEvents(): void {
    this.chunkPreloader.on('chunk-loaded', (e) => {
      this.debug(`ChunkPreloadManager: chunk ${e.chunkIndex} loaded`);
      // Update chunk in chunks array
      if (e.chunkIndex < this.chunks.length && e.audioBuffer) {
        this.chunks[e.chunkIndex].audioBuffer = e.audioBuffer;
        this.chunks[e.chunkIndex].isLoaded = true;
        this.chunks[e.chunkIndex].isLoading = false;
      }
      this.emit('chunk-loaded', e);
    });

    this.chunkPreloader.on('chunk-error', (e) => {
      this.debug(`ChunkPreloadManager: chunk ${e.chunkIndex} error: ${e.error.message}`);
      // Track error with categorization for UI feedback and retry logic
      this.handleChunkError(e.error, e.chunkIndex);
      // Also forward original event for backward compatibility
      this.emit('chunk-error', e);
    });
  }

  /**
   * Load track metadata and prepare for playback
   */
  async loadTrack(trackId: number): Promise<void> {
    this.debug(`Loading track ${trackId}`);
    this.playbackController.setState('loading');
    this.state = 'loading';

    try {
      // Stop current playback
      this.stop();

      // Clear buffer
      this.buffer.clear();

      // Fetch metadata from endpoint
      const metadataUrl = `${this.config.apiBaseUrl}/api/stream/${trackId}/metadata`;
      const response = await fetch(metadataUrl);

      if (!response.ok) {
        throw new Error(`Failed to fetch metadata: ${response.statusText}`);
      }

      this.metadata = (await response.json()) as StreamMetadata;
      this.trackId = trackId;

      // Initialize chunks array with metadata
      const chunkInterval = this.metadata.chunk_interval || this.metadata.chunk_duration;
      this.chunks = [];
      for (let i = 0; i < this.metadata.total_chunks; i++) {
        this.chunks.push({
          index: i,
          startTime: i * chunkInterval,
          endTime: Math.min((i + 1) * chunkInterval, this.metadata.duration),
          audioBuffer: null,
          isLoading: false,
          isLoaded: false
        });
      }

      // Initialize services with metadata
      this.audioController.updateChunkTiming(
        this.metadata.chunk_duration,
        chunkInterval
      );
      this.playbackController.setMetadata(this.metadata);

      // Re-create ChunkPreloadManager with new trackId
      this.chunkPreloader.destroy?.();
      this.chunkPreloader = new ChunkPreloadManager(
        this.buffer,
        this.loadQueue,
        {
          apiBaseUrl: this.config.apiBaseUrl,
          trackId,
          enhanced: this.config.enhanced,
          preset: this.config.preset,
          intensity: this.config.intensity,
          preloadChunks: this.config.preloadChunks
        },
        this.audioController.getAudioContext(),
        this.debug.bind(this)
      );

      // Re-wire events for new preloader instance
      this.wireChunkPreloaderEvents();
      this.chunkPreloader.initChunks(this.metadata.total_chunks);

      this.debug(`Track loaded: ${this.metadata.total_chunks} chunks, ${this.metadata.duration}s`);
      this.playbackController.setState('ready');
      this.state = 'ready';

      // NOTE: Chunk queueing deferred to play() method - AudioContext must be created first
      // (browser autoplay policy prevents creating AudioContext before user gesture)

      this.emit('metadata-loaded', { metadata: this.metadata });

    } catch (error: any) {
      this.debug(`Error loading track: ${error.message}`);
      this.playbackController.setState('error');
      this.state = 'error';
      this.emit('error', error);
      throw error;
    }
  }

  /**
   * Play from current position
   */
  async play(): Promise<void> {
    if (!this.trackId || !this.metadata) {
      throw new Error('No track loaded');
    }

    this.debug('Play requested');

    try {
      // Clear error state when resuming playback (track recovery)
      if (this.errorState.errorCount > 0) {
        this.debug('Clearing error state - playback recovery attempt');
        this.resetErrorState();
      }

      // Ensure AudioContext is initialized (browser autoplay policy)
      // Must be called from user gesture context (button click)
      this.debug('Ensuring AudioContext...');
      const audioContext = this.audioController.ensureAudioContext();
      this.debug(`AudioContext created/ensured, state: ${audioContext.state}`);

      // Resume if suspended
      this.debug('Attempting to resume AudioContext...');
      await this.audioController.resumeAudioContext();

      // Update TimingEngine with audioContext reference
      const currentContext = this.audioController.getAudioContext();
      if (currentContext) {
        this.timingEngine.setAudioContext(currentContext);
        this.chunkPreloader.setAudioContext(currentContext);

        // Now that AudioContext is ready, queue the first chunk for loading
        // This must happen after AudioContext is created (browser autoplay policy)
        this.debug('AudioContext ready, queuing first chunk with CRITICAL priority');
        this.chunkPreloader.queueChunk(0, 0); // Priority 0 = CRITICAL

        // CRITICAL: Wait for chunk 0 to be fully loaded and decoded before playback
        // This prevents race conditions where playback starts with invalid/undefined audioBuffer
        this.debug('Waiting for chunk 0 to load and decode...');
        const chunk0Ready = await this.waitForChunk0();
        if (!chunk0Ready) {
          throw new Error('Chunk 0 failed to load before playback timeout');
        }
        this.debug('Chunk 0 is ready, proceeding with playback');
      } else {
        throw new Error('AudioContext initialization failed');
      }

      // Delegate to PlaybackController
      this.debug('Starting playback via PlaybackController');
      await this.playbackController.play();
      this.state = 'playing';

      // Start timing updates
      this.timingEngine.startTimeUpdates();

      this.debug('Playback started successfully');
      this.emit('playing');
    } catch (error: any) {
      this.debug(`ERROR in play(): ${error.message}`);
      this.state = 'error';
      this.emit('error', error);
      throw error;
    }
  }

  /**
   * Pause playback
   */
  pause(): void {
    if (this.playbackController.getState() !== 'playing') return;

    this.debug('Pause requested');

    // Calculate current position
    const currentTime = this.timingEngine.getCurrentTime();
    this.timingEngine.setPauseTime(currentTime);
    this.playbackController.setCurrentPosition(currentTime);

    // Stop audio
    this.audioController.stopCurrentSource();

    // Update state
    this.playbackController.setState('paused');
    this.state = 'paused';
    this.timingEngine.stopTimeUpdates();

    this.debug(`Paused at ${currentTime.toFixed(2)}s`);
    this.emit('paused');
  }

  /**
   * Stop playback and reset
   */
  private stop(): void {
    this.debug('Stopping playback');
    this.audioController.stopCurrentSource();

    this.timingEngine.setPauseTime(0);
    this.playbackController.setCurrentPosition(0);
    this.playbackController.setCurrentChunkIndex(0);
    this.playbackController.setState('idle');
    this.state = 'idle';

    this.timingEngine.stopTimeUpdates();
  }

  /**
   * Seek to specific time
   */
  async seek(time: number): Promise<void> {
    if (!this.metadata) {
      throw new Error('No track loaded');
    }

    const wasPlaying = this.playbackController.getState() === 'playing';

    this.debug(`Seek to ${time.toFixed(2)}s (was playing: ${wasPlaying})`);

    // Stop current playback
    this.audioController.stopCurrentSource();
    this.timingEngine.stopTimeUpdates();

    // Calculate target chunk and offset
    const chunkInterval = this.metadata.chunk_interval || this.metadata.chunk_duration;
    const targetChunk = Math.floor(time / chunkInterval);
    const offset = time - (targetChunk * chunkInterval);

    this.debug(`Seeking to chunk ${targetChunk} + ${offset.toFixed(2)}s offset`);

    // Queue chunks with appropriate priorities
    this.chunkPreloader.queueChunk(targetChunk, 2); // SEEK_TARGET
    if (targetChunk > 0) {
      this.chunkPreloader.queueChunk(targetChunk - 1, 3); // ADJACENT (prev)
    }
    if (targetChunk + 1 < this.chunks.length) {
      this.chunkPreloader.queueChunk(targetChunk + 1, 3); // ADJACENT (next)
    }

    // Update timing reference
    this.timingEngine.setPauseTime(time);
    this.playbackController.setCurrentPosition(time);
    this.playbackController.setCurrentChunkIndex(targetChunk);

    // If was playing, wait a bit for chunk to load then resume
    if (wasPlaying) {
      // Wait up to 2 seconds for target chunk to load
      const maxWait = 2000;
      const startTime = Date.now();
      while (
        (!this.chunks[targetChunk]?.audioBuffer) &&
        Date.now() - startTime < maxWait
      ) {
        await new Promise(resolve => setTimeout(resolve, 50));
      }

      // Resume playback
      await this.playChunkInternal(targetChunk, offset);
      this.timingEngine.startTimeUpdates();
      this.playbackController.setState('playing');
      this.state = 'playing';
    }

    this.emit('seeked');
  }

  /**
   * Internal: Play a specific chunk
   * Called by AudioController or when transitioning between chunks
   */
  private async playChunkInternal(chunkIndex: number, offset: number = 0): Promise<void> {
    if (chunkIndex >= this.chunks.length) {
      this.debug(`playChunkInternal: chunk ${chunkIndex} out of bounds`);
      return;
    }

    const chunk = this.chunks[chunkIndex];

    // If chunk not loaded, queue it with CRITICAL priority and wait
    if (!chunk.audioBuffer || !chunk.isLoaded) {
      this.debug(`playChunkInternal: chunk ${chunkIndex} not loaded, queuing with CRITICAL priority`);
      this.chunkPreloader.queueChunk(chunkIndex, 0);

      // Wait up to 15 seconds for load (accounts for chunk processing + network latency)
      const maxWait = 30000; // 30s timeout for chunk loading
      const startTime = Date.now();
      while (!this.chunks[chunkIndex].audioBuffer && Date.now() - startTime < maxWait) {
        await new Promise(resolve => setTimeout(resolve, 50));
      }

      if (!this.chunks[chunkIndex].audioBuffer) {
        throw new Error(`Chunk ${chunkIndex} failed to load within timeout`);
      }
    }

    const audioBuffer = this.chunks[chunkIndex].audioBuffer;
    if (!audioBuffer) {
      throw new Error(`Chunk ${chunkIndex} audioBuffer is null`);
    }

    // Delegate to AudioContextController
    const isPlaying = this.playbackController.getState() === 'playing';
    await this.audioController.playChunk(
      chunkIndex,
      audioBuffer,
      offset,
      isPlaying,
      this.chunks.length,
      this.metadata || undefined
    );

    // Update PlaybackController state
    this.playbackController.setCurrentChunkIndex(chunkIndex);

    // Queue next chunk for preload
    if (chunkIndex + 1 < this.chunks.length) {
      this.chunkPreloader.queueChunk(chunkIndex + 1, 1); // IMMEDIATE
    }

    this.debug(`playChunkInternal: playing chunk ${chunkIndex} from ${offset.toFixed(2)}s`);
  }

  /**
   * Toggle audio enhancement
   */
  async setEnhanced(enabled: boolean, preset?: string): Promise<void> {
    const oldEnhanced = this.config.enhanced;
    const oldPreset = this.config.preset;

    this.config.enhanced = enabled;
    if (preset) {
      this.config.preset = preset;
    }

    // Only reload if settings changed
    if (oldEnhanced === enabled && (!preset || oldPreset === preset)) {
      return;
    }

    this.debug(`Enhancement changed: enabled=${enabled}, preset=${preset || this.config.preset}`);

    if (!this.trackId || !this.metadata) {
      return;
    }

    const wasPlaying = this.playbackController.getState() === 'playing';
    const currentTime = this.getCurrentTime();

    this.debug(`Flushing buffer at ${currentTime.toFixed(2)}s, wasPlaying=${wasPlaying}`);

    // Stop playback
    this.audioController.stopCurrentSource();
    this.timingEngine.stopTimeUpdates();

    // Clear buffer
    this.buffer.clear();

    // Re-create ChunkPreloadManager with updated config
    this.chunkPreloader.destroy?.();
    this.chunkPreloader = new ChunkPreloadManager(
      this.buffer,
      this.loadQueue,
      {
        apiBaseUrl: this.config.apiBaseUrl,
        trackId: this.trackId,
        enhanced: this.config.enhanced,
        preset: this.config.preset,
        intensity: this.config.intensity,
        preloadChunks: this.config.preloadChunks
      },
      this.audioController.getAudioContext(),
      this.debug.bind(this)
    );
    this.wireChunkPreloaderEvents();
    this.chunkPreloader.initChunks(this.chunks.length);

    if (wasPlaying) {
      // Preload current and adjacent chunks
      const chunkInterval = this.metadata.chunk_interval || this.metadata.chunk_duration;
      const currentChunkIndex = Math.floor(currentTime / chunkInterval);

      this.chunkPreloader.queueChunk(currentChunkIndex, 0); // CRITICAL
      if (currentChunkIndex + 1 < this.chunks.length) {
        this.chunkPreloader.queueChunk(currentChunkIndex + 1, 1); // IMMEDIATE
      }

      // Wait for current chunk to load using event-driven approach (not polling)
      const chunkLoaded = await this.waitForChunk(currentChunkIndex, 3000);
      if (!chunkLoaded) {
        this.debug(`[ENHANCE] Timeout waiting for chunk ${currentChunkIndex}, resuming anyway`);
      }

      // Resume from current time
      await this.seek(currentTime);
      await this.play();

      this.debug(`Enhancement toggle complete, resumed playback`);
    }
  }

  /**
   * Set preset
   */
  async setPreset(preset: string): Promise<void> {
    await this.setEnhanced(this.config.enhanced, preset);
  }

  /**
   * Set volume (0.0 - 1.0)
   */
  setVolume(volume: number): void {
    this.volume = Math.max(0, Math.min(1, volume));
    this.audioController.setVolume(this.volume);
    this.debug(`Volume set to ${(this.volume * 100).toFixed(0)}%`);
  }

  /**
   * Get current playback time
   */
  getCurrentTime(): number {
    if (this.playbackController.getState() === 'playing') {
      const currentTime = this.timingEngine.getCurrentTime();
      return Math.min(currentTime, this.metadata?.duration || 0);
    }
    return this.playbackController.getCurrentPosition();
  }

  /**
   * Get track duration
   */
  getDuration(): number {
    return this.metadata?.duration || 0;
  }

  /**
   * Get current playback time with debug info
   */
  getCurrentTimeDebug(): { time: number; audioCtxTime: number; trackStartTime: number; difference: number } {
    return this.timingEngine.getCurrentTimeDebug();
  }

  /**
   * Get current playback state
   */
  getState(): PlaybackState {
    return this.state;
  }

  /**
   * Get track metadata
   */
  getMetadata(): StreamMetadata | null {
    return this.metadata;
  }

  /**
   * Categorize error and track failed chunks for retry logic
   * Emits categorized error event for UI feedback
   */
  private handleChunkError(error: any, chunkIndex: number): void {
    // Categorize error type
    const errorMessage = error?.message || String(error);
    let errorType: 'network' | 'decode' | 'timeout' | 'audiocontext' | 'unknown' = 'unknown';

    if (errorMessage.includes('Failed to fetch') || errorMessage.includes('Network')) {
      errorType = 'network';
    } else if (errorMessage.includes('decode')) {
      errorType = 'decode';
    } else if (errorMessage.includes('timeout') || errorMessage.includes('failed to load')) {
      errorType = 'timeout';
    } else if (errorMessage.includes('AudioContext')) {
      errorType = 'audiocontext';
    }

    // Update error state
    const now = Date.now();
    this.errorState.lastError = error;
    this.errorState.errorType = errorType;
    this.errorState.errorCount++;
    this.errorState.lastErrorTime = now;
    this.errorState.failedChunks.add(chunkIndex);

    this.debug(
      `[ERROR] Chunk ${chunkIndex} failed (${errorType}): ${errorMessage} ` +
      `(total errors: ${this.errorState.errorCount})`
    );

    // Emit categorized error event for UI feedback
    this.emit('chunk-error-detailed', {
      chunkIndex,
      errorType,
      errorMessage,
      failedChunkCount: this.errorState.failedChunks.size,
      totalErrors: this.errorState.errorCount
    });
  }

  /**
   * Get current error state for UI feedback
   */
  getErrorState(): {
    lastError: Error | null;
    errorType: string;
    failedChunkCount: number;
    totalErrorCount: number;
  } {
    return {
      lastError: this.errorState.lastError,
      errorType: this.errorState.errorType,
      failedChunkCount: this.errorState.failedChunks.size,
      totalErrorCount: this.errorState.errorCount
    };
  }

  /**
   * Clear error state when resuming playback successfully
   */
  private resetErrorState(): void {
    this.errorState.lastError = null;
    this.errorState.errorType = 'unknown';
    this.errorState.failedChunks.clear();
    this.errorState.errorCount = 0;
    this.errorState.lastErrorTime = 0;
    this.debug('[ERROR] Error state cleared - playback recovery successful');
  }

  /**
   * Check if chunk failed previously (for retry logic)
   */
  didChunkFail(chunkIndex: number): boolean {
    return this.errorState.failedChunks.has(chunkIndex);
  }

  /**
   * Cleanup resources
   */
  cleanup(): void {
    this.debug('Cleaning up player resources');
    this.stop();
    this.timingEngine.destroy?.();
    this.chunkPreloader.destroy();
    this.audioController.destroy?.();
    this.playbackController.destroy?.();
    this.buffer.clear();
    this.listeners.clear();
    this.errorState.failedChunks.clear();
  }

  /**
   * Event system: register listener
   */
  on(event: string, callback: EventCallback): () => void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback);

    // Return unsubscribe function
    return () => {
      this.listeners.get(event)?.delete(callback);
    };
  }

  /**
   * Event system: unregister listener
   */
  off(event: string, callback: EventCallback): void {
    this.listeners.get(event)?.delete(callback);
  }

  /**
   * Event system: emit event
   */
  private emit(event: string, data?: any): void {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          this.debug(`Error in event listener for '${event}': ${error}`);
        }
      });
    }
  }

  /**
   * Wait for chunk 0 to be fully loaded and decoded
   * Critical for preventing race conditions during playback initialization
   * @returns true if chunk 0 is ready, false if timeout or error
   */
  /**
   * Event-driven wait for a specific chunk to load
   * Replaces polling with proper event listening for better reliability
   */
  private async waitForChunk(chunkIndex: number, maxWaitTime: number = 3000): Promise<boolean> {
    return new Promise((resolve) => {
      let timeoutId: NodeJS.Timeout | null = null;

      // Check if chunk is already loaded
      const chunk = this.chunkPreloader.getChunk(chunkIndex);
      if (chunk && chunk.isLoaded && chunk.audioBuffer) {
        this.debug(`[WAIT] Chunk ${chunkIndex} already loaded`);
        resolve(true);
        return;
      }

      // Set up timeout
      timeoutId = setTimeout(() => {
        this.debug(`[WAIT] Chunk ${chunkIndex} failed to load within ${maxWaitTime}ms timeout`);
        this.chunkPreloader.off('chunk-loaded', onChunkLoaded);
        resolve(false);
      }, maxWaitTime);

      // Listen for chunk loaded event
      const onChunkLoaded = (data: any) => {
        if (data.chunkIndex === chunkIndex) {
          this.debug(`[WAIT] Chunk ${chunkIndex} loaded event received`);
          if (timeoutId) clearTimeout(timeoutId);
          this.chunkPreloader.off('chunk-loaded', onChunkLoaded);
          resolve(true);
        }
      };

      this.chunkPreloader.on('chunk-loaded', onChunkLoaded);
      this.debug(`[WAIT] Waiting for chunk ${chunkIndex} loaded event (timeout: ${maxWaitTime}ms)...`);
    });
  }

  private async waitForChunk0(): Promise<boolean> {
    return this.waitForChunk(0, 30000);
  }

  /**
   * Debug logging
   */
  private debug(message: string): void {
    if (this.config.debug) {
      console.log(`[UnifiedWebMAudioPlayer] ${message}`);
    }
  }
}

export default UnifiedWebMAudioPlayer;
