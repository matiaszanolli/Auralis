/**
 * ChunkPreloadManager - Chunk loading and preloading orchestration
 *
 * Responsibility: Load audio chunks in priority order, with caching and retries
 *
 * Extracted from UnifiedWebMAudioPlayer for:
 * - Clear separation of chunk loading concern
 * - Testable preload logic
 * - Independent chunk management strategy
 *
 * Key Features:
 * - Priority-based loading (CRITICAL → IMMEDIATE → SEEK_TARGET → ADJACENT → BACKGROUND)
 * - LRU buffer caching to avoid redundant decode operations
 * - Automatic background preloading of adjacent chunks
 * - Error handling with graceful degradation
 * - Queue-based processing to avoid blocking
 */

import { ChunkLoadPriorityQueue, ChunkLoadPriority } from './ChunkLoadPriorityQueue';
import { MultiTierWebMBuffer } from './MultiTierWebMBuffer';

export interface ChunkInfo {
  isLoaded: boolean;
  isLoading: boolean;
  audioBuffer: AudioBuffer | null;
}

export interface PreloadConfig {
  apiBaseUrl: string;
  trackId: number;
  enhanced: boolean;
  preset: string;
  intensity: number;
  preloadChunks: number; // Number of adjacent chunks to preload
}

type EventCallback = (data?: any) => void;

export class ChunkPreloadManager {
  private queue: ChunkLoadPriorityQueue;
  private buffer: MultiTierWebMBuffer;
  private chunks: ChunkInfo[] = [];
  private config: PreloadConfig;
  private audioContext: AudioContext | null = null;
  private queueProcessorRunning = false;
  private eventCallbacks = new Map<string, Set<EventCallback>>();
  private debug: (msg: string) => void = () => {};

  // Retry logic with exponential backoff
  private retryState: Map<number, { attempts: number; lastAttemptTime: number }> = new Map();
  private readonly MAX_RETRIES = 3;
  private readonly BASE_RETRY_DELAY_MS = 500; // Start with 500ms, exponential backoff 2x

  constructor(
    buffer: MultiTierWebMBuffer,
    queue: ChunkLoadPriorityQueue,
    config: PreloadConfig,
    audioContext: AudioContext | null = null,
    debugFn?: (msg: string) => void
  ) {
    this.buffer = buffer;
    this.queue = queue;
    this.config = config;
    this.audioContext = audioContext;
    if (debugFn) {
      this.debug = debugFn;
    }
  }

  /**
   * Initialize chunks array
   * Called when track metadata is loaded with chunk count
   */
  initChunks(chunkCount: number): void {
    this.chunks = Array.from({ length: chunkCount }, () => ({
      isLoaded: false,
      isLoading: false,
      audioBuffer: null
    }));
    this.debug(`[PRELOAD] Initialized ${chunkCount} chunks`);
  }

  /**
   * Update audio context (if it changes during playback)
   * If there are queued chunks waiting, retry processing now that AudioContext is available
   */
  setAudioContext(audioContext: AudioContext): void {
    this.audioContext = audioContext;
    this.debug(`[PRELOAD] AudioContext set, queue size: ${this.queue.getSize()}`);

    // If there are items in the queue and processor isn't running, start it now
    if (this.queue.getSize() > 0 && !this.queueProcessorRunning) {
      this.debug(`[PRELOAD] Queue has items and processor not running, starting processor`);
      this.processLoadQueue().catch((error: any) => {
        this.debug(`[PRELOAD] Queue processor error after AudioContext set: ${error.message}`);
        this.emit('queue-error', { error });
      });
    }
  }

  /**
   * Queue a chunk for loading with given priority
   *
   * @param chunkIndex - Index of chunk to load
   * @param priority - Priority level (0=CRITICAL, 4=BACKGROUND)
   */
  queueChunk(chunkIndex: number, priority: number = ChunkLoadPriority.BACKGROUND): void {
    if (chunkIndex >= this.chunks.length) return;

    const chunk = this.chunks[chunkIndex];

    // Only skip if already loaded with valid audioBuffer
    // If loading or previously failed, we should retry
    if (chunk.isLoaded && chunk.audioBuffer) {
      this.debug(`[PRELOAD] Chunk ${chunkIndex} already loaded, skipping`);
      return;
    }

    // Add to priority queue instead of loading immediately
    this.debug(
      `[PRELOAD] Enqueueing chunk ${chunkIndex} with priority ${priority} ` +
      `(queue size before: ${this.queue.getSize()})`
    );
    this.queue.enqueue(chunkIndex, priority);
    this.debug(`[PRELOAD] Queue size after: ${this.queue.getSize()}`);

    // Start queue processor if not already running
    if (!this.queueProcessorRunning) {
      this.debug(`[PRELOAD] Starting queue processor`);
      // Fire and forget with error handling
      this.processLoadQueue().catch((error: any) => {
        this.debug(`[PRELOAD] Queue processor error: ${error.message}`);
        this.emit('queue-error', { error });
      });
    } else {
      this.debug(`[PRELOAD] Queue processor already running`);
    }
  }

  /**
   * Get current queue size
   */
  getQueueSize(): number {
    return this.queue.getSize();
  }

  /**
   * Check if chunk is currently loading
   */
  isLoading(chunkIndex: number): boolean {
    return this.queue.isLoading(chunkIndex);
  }

  /**
   * Clear all queued chunks with priority >= threshold
   * Used when seeking to discard low-priority background loads
   */
  clearLowerPriority(priority: number): void {
    this.queue.clearLowerPriority(priority);
    this.debug(`[PRELOAD] Cleared all chunks with priority >= ${priority}`);
  }

  /**
   * Clear entire preload queue
   * Used when stopping playback or loading new track
   */
  clearQueue(): void {
    this.queue.clear();
    this.debug(`[PRELOAD] Queue cleared`);
  }

  /**
   * Process the priority queue, loading chunks in order of priority
   * This ensures seeks are prioritized over background preloads
   * Runs until queue is empty
   */
  private async processLoadQueue(): Promise<void> {
    if (this.queueProcessorRunning) {
      this.debug(`[QUEUE] Queue processor already running, skipping`);
      return;
    }

    this.queueProcessorRunning = true;
    this.debug(`[QUEUE] Queue processor started with ${this.queue.getSize()} items`);

    // Wait for AudioContext to be available if not yet initialized
    // This handles race conditions where queue is added before AudioContext exists
    if (!this.audioContext) {
      this.debug(`[QUEUE] AudioContext not yet initialized, waiting...`);
      let waitCount = 0;
      const maxWait = 50; // Wait up to 5 seconds (50 * 100ms)
      while (!this.audioContext && waitCount < maxWait) {
        await new Promise(resolve => setTimeout(resolve, 100));
        waitCount++;
      }

      if (!this.audioContext) {
        this.queueProcessorRunning = false;
        this.debug(`[QUEUE] AudioContext failed to initialize within timeout, will retry when AudioContext is set`);
        // Don't throw - allow retry when AudioContext becomes available
        return;
      }
      this.debug(`[QUEUE] AudioContext available after ${waitCount * 100}ms wait`);
    }

    try {
      while (this.queue.getSize() > 0) {
        const nextItem = this.queue.dequeue();
        if (!nextItem) break;

        const { chunkIndex, priority } = nextItem;
        this.debug(
          `[QUEUE] Processing chunk ${chunkIndex} priority ${priority} ` +
          `(queue size: ${this.queue.getSize()})`
        );

        // Skip if already loaded or currently loading
        const chunk = this.chunks[chunkIndex];
        if (chunk.isLoaded && chunk.audioBuffer) {
          this.debug(`[QUEUE] Chunk ${chunkIndex} already loaded, skipping`);
          continue;
        }
        if (chunk.isLoading) {
          this.debug(`[QUEUE] Chunk ${chunkIndex} already loading, skipping`);
          continue;
        }

        // Mark as loading and load in background
        chunk.isLoading = true;
        this.debug(`[P${priority}] Loading chunk ${chunkIndex}/${this.chunks.length}`);

        // Create load promise without awaiting (fire and forget)
        // Add error handling to catch and emit errors from async loading
        const loadPromise = this.loadChunkInternal(chunkIndex, priority)
          .catch((error: any) => {
            this.debug(`[P${priority}] Caught async error loading chunk ${chunkIndex}: ${error.message}`);
            // Error is already handled in loadChunkInternal catch block and emitted
            // This catch is here to prevent unhandled promise rejection warnings
          });
        this.queue.markActive(chunkIndex, loadPromise);

        // Don't await - let loads happen in parallel
        // But track them so we know they're happening
      }

      this.debug(
        `[QUEUE] Queue processor finished, ` +
        `${this.queue.getSize()} items remaining, ` +
        `${this.queue.getLoadingCount()} still loading`
      );
    } finally {
      this.queueProcessorRunning = false;
    }
  }

  /**
   * Internal: Load a single chunk
   * Handles fetching, decoding, caching, and background preloading
   */
  private async loadChunkInternal(chunkIndex: number, priority: number): Promise<void> {
    const chunk = this.chunks[chunkIndex];

    try {
      // Check buffer cache first
      const cacheKey = this.buffer.getCacheKey(
        this.config.trackId,
        chunkIndex,
        this.config.enhanced,
        this.config.preset
      );

      let audioBuffer = this.buffer.get(cacheKey);

      if (!audioBuffer) {
        // Fetch WAV chunk from endpoint (Web Audio API compatible format)
        const chunkUrl =
          `${this.config.apiBaseUrl}/api/stream/${this.config.trackId}/chunk/${chunkIndex}` +
          `?enhanced=${this.config.enhanced}&preset=${this.config.preset}` +
          `&intensity=${this.config.intensity}`;

        this.debug(`[P${priority}] Fetching chunk from: ${chunkUrl}`);

        let response: Response;
        try {
          response = await fetch(chunkUrl);
        } catch (fetchError: any) {
          this.debug(`[P${priority}] Fetch failed: ${fetchError.message}`);
          throw new Error(`Failed to fetch chunk ${chunkIndex}: ${fetchError.message}`);
        }

        this.debug(`[P${priority}] Fetch response status: ${response.status} ${response.statusText}`);

        if (!response.ok) {
          throw new Error(`Failed to fetch chunk ${chunkIndex}: ${response.statusText}`);
        }

        const cacheHeader = response.headers.get('X-Cache-Tier');
        this.debug(`[P${priority}] Chunk ${chunkIndex} cache: ${cacheHeader}`);

        const arrayBuffer = await response.arrayBuffer();
        this.debug(`[P${priority}] Chunk ${chunkIndex}: received ${arrayBuffer.byteLength} bytes`);

        if (arrayBuffer.byteLength === 0) {
          throw new Error(`Chunk ${chunkIndex} returned empty data (0 bytes)`);
        }

        // Verify RIFF/WAV header for debugging
        const dataView = new DataView(arrayBuffer);
        const riffHeader = String.fromCharCode(
          dataView.getUint8(0),
          dataView.getUint8(1),
          dataView.getUint8(2),
          dataView.getUint8(3)
        );
        const waveHeader = String.fromCharCode(
          dataView.getUint8(8),
          dataView.getUint8(9),
          dataView.getUint8(10),
          dataView.getUint8(11)
        );
        this.debug(
          `[P${priority}] WAV header check: RIFF='${riffHeader}' WAVE='${waveHeader}' ` +
          `(${arrayBuffer.byteLength} bytes)`
        );

        this.debug(`[P${priority}] Decoding ${arrayBuffer.byteLength} bytes for chunk ${chunkIndex}...`);

        // Decode WAV to AudioBuffer using Web Audio API
        if (!this.audioContext) {
          throw new Error('AudioContext not available for decoding');
        }

        try {
          audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);
          this.debug(
            `[P${priority}] Decoded chunk ${chunkIndex}: ` +
            `${audioBuffer.duration.toFixed(2)}s, ` +
            `${audioBuffer.numberOfChannels} channels, ` +
            `${audioBuffer.sampleRate}Hz`
          );
        } catch (decodeError: any) {
          this.debug(
            `[P${priority}] Decode error details: ${decodeError.name} - ${decodeError.message}`
          );
          throw new Error(
            `Failed to decode chunk ${chunkIndex}: ${decodeError.message || 'Unknown decode error'}`
          );
        }

        // Cache decoded buffer for future playback
        this.buffer.set(cacheKey, audioBuffer);
      } else {
        this.debug(`[P${priority}] Chunk ${chunkIndex} from buffer cache`);
      }

      // Update all state atomically (before event emission)
      // This ensures event listeners see consistent state
      chunk.audioBuffer = audioBuffer;
      chunk.isLoaded = true;
      chunk.isLoading = false;

      this.debug(`[P${priority}] Chunk ${chunkIndex} ready (${audioBuffer.duration.toFixed(2)}s)`);

      // Clear retry state on successful load
      this.clearRetryState(chunkIndex);

      // Now emit event - state is fully consistent
      this.emit('chunk-loaded', { chunkIndex, audioBuffer });

      // Queue next chunks for background preload with lower priority
      if (priority <= ChunkLoadPriority.SEEK_TARGET) {
        // If this was a high-priority chunk, queue the next chunks for preloading
        for (let i = 1; i <= this.config.preloadChunks; i++) {
          const nextIdx = chunkIndex + i;
          if (nextIdx < this.chunks.length && !this.queue.isQueued(nextIdx)) {
            this.queue.enqueue(nextIdx, ChunkLoadPriority.BACKGROUND);
          }
        }
      }
    } catch (error: any) {
      // Update error state atomically (before event emission)
      // This ensures event listeners see consistent state
      chunk.isLoading = false;
      chunk.isLoaded = false;
      chunk.audioBuffer = null; // Clear any partial state

      this.debug(`[P${priority}] Error loading chunk ${chunkIndex}: ${error.message}`);

      // Schedule automatic retry with exponential backoff if attempts remaining
      this.scheduleRetry(chunkIndex, priority, error);

      // Now emit error event - state is fully consistent
      this.emit('chunk-error', { chunkIndex, error });
      // Continue - chunk can be retried in future queue cycle if requested
    }
  }

  /**
   * Schedule automatic retry for a failed chunk with exponential backoff
   * Reduces retry spam on persistent failures by using exponential delays
   */
  private scheduleRetry(chunkIndex: number, priority: number, error: any): void {
    let retryInfo = this.retryState.get(chunkIndex);

    // Initialize or increment attempt counter
    if (!retryInfo) {
      retryInfo = { attempts: 0, lastAttemptTime: 0 };
      this.retryState.set(chunkIndex, retryInfo);
    }

    const attempts = retryInfo.attempts;

    // Check if we've exceeded max retries
    if (attempts >= this.MAX_RETRIES) {
      this.debug(
        `[RETRY] Chunk ${chunkIndex} exceeded max retries (${this.MAX_RETRIES}), giving up. ` +
        `Error: ${error.message}`
      );
      return;
    }

    // Calculate exponential backoff delay (500ms, 1s, 2s)
    const delayMs = this.BASE_RETRY_DELAY_MS * Math.pow(2, attempts);

    // Increment attempt counter
    retryInfo.attempts++;
    retryInfo.lastAttemptTime = Date.now();

    this.debug(
      `[RETRY] Chunk ${chunkIndex} failed (attempt ${retryInfo.attempts}/${this.MAX_RETRIES}). ` +
      `Scheduling retry in ${delayMs}ms... Error: ${error.message}`
    );

    // Schedule retry with backoff delay
    setTimeout(() => {
      this.debug(
        `[RETRY] Retrying chunk ${chunkIndex} (attempt ${retryInfo.attempts}/${this.MAX_RETRIES})`
      );
      // Re-queue with original priority (or slightly elevated to skip line)
      this.queueChunk(chunkIndex, Math.max(priority - 1, 0));
    }, delayMs);
  }

  /**
   * Clear retry state for a chunk (called on successful load)
   */
  private clearRetryState(chunkIndex: number): void {
    if (this.retryState.has(chunkIndex)) {
      const attempts = this.retryState.get(chunkIndex)!.attempts;
      if (attempts > 0) {
        this.debug(`[RETRY] Chunk ${chunkIndex} recovered after ${attempts} failed attempt(s)`);
      }
      this.retryState.delete(chunkIndex);
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
   * Event system: Emit event to all listeners
   */
  private emit(event: string, data?: any): void {
    this.eventCallbacks.get(event)?.forEach(callback => {
      try {
        callback(data);
      } catch (error) {
        console.error(`[ChunkPreloadManager] Error in ${event} callback:`, error);
      }
    });
  }

  /**
   * Clean up resources
   */
  destroy(): void {
    this.clearQueue();
    this.chunks = [];
    this.eventCallbacks.clear();
    this.retryState.clear(); // Clear retry state to prevent memory leaks
    this.queueProcessorRunning = false; // CRITICAL: Reset flag to ensure queue processing can restart
  }
}
