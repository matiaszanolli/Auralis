/**
 * UnifiedWebMAudioPlayer - Single Player with Web Audio API
 * ===========================================================
 *
 * NEW ARCHITECTURE (Phase 2):
 * - Always fetches WebM/Opus chunks from /api/stream endpoint
 * - Decodes to AudioBuffer using Web Audio API
 * - Single player, single format, zero conflicts
 * - Optional client-side DSP processing
 *
 * Replaces dual MSE/HTML5 player with unified approach:
 * 1. Backend always serves WebM/Opus (Phase 1 ✅)
 * 2. Frontend decodes with Web Audio API (this file)
 * 3. Client-side DSP optional (future enhancement)
 *
 * @copyright (C) 2025 Auralis Team
 * @license GPLv3
 */

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
 * Multi-Tier WebM Buffer Manager
 * Caches decoded AudioBuffer instances for instant playback
 */
class MultiTierWebMBuffer {
  private cache: Map<string, AudioBuffer> = new Map();
  private maxSize: number = 10; // Keep last 10 chunks

  getCacheKey(trackId: number, chunkIdx: number, enhanced: boolean, preset: string): string {
    return `${trackId}_${chunkIdx}_${enhanced}_${preset}`;
  }

  get(key: string): AudioBuffer | null {
    return this.cache.get(key) || null;
  }

  set(key: string, buffer: AudioBuffer): void {
    // Simple LRU: if cache full, delete oldest entry
    if (this.cache.size >= this.maxSize) {
      const firstKey = this.cache.keys().next().value;
      if (firstKey) this.cache.delete(firstKey);
    }
    this.cache.set(key, buffer);
  }

  clear(): void {
    this.cache.clear();
  }

  getSize(): number {
    return this.cache.size;
  }
}

/**
 * Priority Queue for Chunk Loading
 * Ensures critical chunks (needed for playback) are loaded before background chunks
 *
 * Priority levels:
 * 1. CRITICAL (0): Chunk currently being played
 * 2. IMMEDIATE (1): Next chunk needed for continuous playback
 * 3. SEEK_TARGET (2): Chunk user just seeked to
 * 4. ADJACENT (3): Chunks ±1 around current position
 * 5. BACKGROUND (4): All other chunks
 */
class ChunkLoadPriorityQueue {
  private queue: Array<{ chunkIndex: number; priority: number; timestamp: number }> = [];
  private isProcessing = false;
  private activeLoads = new Map<number, Promise<void>>();

  /**
   * Add or update chunk in queue with given priority
   * Lower number = higher priority
   */
  enqueue(chunkIndex: number, priority: number): void {
    // Remove existing entry if present
    this.queue = this.queue.filter(item => item.chunkIndex !== chunkIndex);

    // Add with new priority and current timestamp
    this.queue.push({
      chunkIndex,
      priority,
      timestamp: Date.now()
    });

    // Sort by priority (ascending), then by timestamp (descending - newer first)
    this.queue.sort((a, b) => {
      if (a.priority !== b.priority) {
        return a.priority - b.priority; // Lower priority number first
      }
      return b.timestamp - a.timestamp; // Newer timestamps first
    });
  }

  /**
   * Get next chunk to load based on priority
   */
  dequeue(): { chunkIndex: number; priority: number } | null {
    if (this.queue.length === 0) return null;

    const item = this.queue.shift();
    if (!item) return null;

    return {
      chunkIndex: item.chunkIndex,
      priority: item.priority
    };
  }

  /**
   * Clear all chunks with given priority or lower (less urgent)
   */
  clearLowerPriority(priority: number): void {
    this.queue = this.queue.filter(item => item.priority <= priority);
  }

  /**
   * Clear entire queue
   */
  clear(): void {
    this.queue = [];
  }

  /**
   * Check if chunk is already queued or loading
   */
  isQueued(chunkIndex: number): boolean {
    return this.queue.some(item => item.chunkIndex === chunkIndex) ||
           this.activeLoads.has(chunkIndex);
  }

  /**
   * Get current queue size
   */
  getSize(): number {
    return this.queue.length;
  }

  /**
   * Mark load as active
   */
  markActive(chunkIndex: number, promise: Promise<void>): void {
    this.activeLoads.set(chunkIndex, promise);
    promise.finally(() => {
      this.activeLoads.delete(chunkIndex);
    });
  }

  /**
   * Check if chunk is currently loading
   */
  isLoading(chunkIndex: number): boolean {
    return this.activeLoads.has(chunkIndex);
  }
}

/**
 * Unified WebM Audio Player
 * Uses Web Audio API for all playback
 */
export class UnifiedWebMAudioPlayer {
  private config: Required<UnifiedWebMAudioPlayerConfig>;
  private audioContext: AudioContext | null = null;
  private buffer: MultiTierWebMBuffer;
  private loadQueue: ChunkLoadPriorityQueue;

  // Track state
  private trackId: number | null = null;
  private metadata: StreamMetadata | null = null;
  private chunks: ChunkInfo[] = [];

  // Playback state
  private state: PlaybackState = 'idle';
  private currentSource: AudioBufferSourceNode | null = null;
  private currentChunkIndex: number = 0;
  private startTime: number = 0;
  private currentChunkOffset: number = 0;  // Offset within current chunk (for seeking)
  private pauseTime: number = 0;
  private volume: number = 1.0;

  // Gain node for volume control
  private gainNode: GainNode | null = null;

  // Event system
  private listeners: Map<string, Set<EventCallback>> = new Map();

  // Queue processor
  private queueProcessorRunning = false;

  constructor(config: UnifiedWebMAudioPlayerConfig = {}) {
    this.config = {
      apiBaseUrl: config.apiBaseUrl || 'http://localhost:8765',
      chunkDuration: config.chunkDuration || 10, // Reduced from 30s → 10s for Beta.9 Phase 2
      enhanced: config.enhanced !== undefined ? config.enhanced : true,
      preset: config.preset || 'adaptive',
      intensity: config.intensity !== undefined ? config.intensity : 1.0,
      preloadChunks: config.preloadChunks || 2,
      debug: config.debug || false
    };

    // Initialize buffer
    this.buffer = new MultiTierWebMBuffer();

    // Initialize priority queue
    this.loadQueue = new ChunkLoadPriorityQueue();

    // NOTE: AudioContext is NOT created in constructor to comply with browser autoplay policy
    // It will be lazily created on first user gesture (play() call)
    this.debug('UnifiedWebMAudioPlayer initialized (AudioContext deferred until first play)');
  }

  /**
   * Lazily initialize AudioContext on first user gesture
   * Required by browser autoplay policy
   */
  private ensureAudioContext(): void {
    if (!this.audioContext) {
      this.audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
      this.gainNode = this.audioContext.createGain();
      this.gainNode!.connect(this.audioContext.destination);
      this.debug('AudioContext created on first user gesture');
    }
  }

  /**
   * Load track metadata and prepare for playback
   */
  async loadTrack(trackId: number): Promise<void> {
    this.debug(`Loading track ${trackId}`);
    this.setState('loading');

    try {
      // Stop current playback
      this.stop();

      // Clear buffer
      this.buffer.clear();

      // Fetch metadata from NEW endpoint
      const metadataUrl = `${this.config.apiBaseUrl}/api/stream/${trackId}/metadata`;
      const response = await fetch(metadataUrl);

      if (!response.ok) {
        throw new Error(`Failed to fetch metadata: ${response.statusText}`);
      }

      this.metadata = (await response.json()) as StreamMetadata;
      this.trackId = trackId;

      // Initialize chunks
      // With overlap model (15s chunks, 10s intervals):
      //   Chunk 0: startTime=0s, endTime=10s (plays audio from 0-15s)
      //   Chunk 1: startTime=10s, endTime=20s (plays audio from 10-25s)
      //   Chunk 2: startTime=20s, endTime=30s (plays audio from 20-35s)
      const chunkInterval = this.metadata.chunk_interval || this.metadata.chunk_duration;
      this.chunks = [];
      for (let i = 0; i < this.metadata.total_chunks; i++) {
        this.chunks.push({
          index: i,
          startTime: i * chunkInterval,  // Use interval, not duration
          endTime: Math.min((i + 1) * chunkInterval, this.metadata.duration),  // Use interval, not duration
          audioBuffer: null,
          isLoading: false,
          isLoaded: false
        });
      }

      this.debug(`Track loaded: ${this.metadata.total_chunks} chunks, ${this.metadata.duration}s`);
      this.setState('ready');

      // Preload first chunk
      await this.preloadChunk(0);

    } catch (error: any) {
      this.debug(`Error loading track: ${error.message}`);
      this.setState('error');
      this.emit('error', error);
      throw error;
    }
  }

  /**
   * Preload a chunk (fetch + decode)
   * Now integrates with priority queue to respect seek operations
   */
  private async preloadChunk(chunkIndex: number, priority: number = 4): Promise<void> {
    if (chunkIndex >= this.chunks.length) return;

    const chunk = this.chunks[chunkIndex];
    // Only skip if already loaded (with valid audioBuffer)
    // If loading or previously failed, we should retry
    if (chunk.isLoaded && chunk.audioBuffer) return;

    // Add to priority queue instead of loading immediately
    this.loadQueue.enqueue(chunkIndex, priority);

    // Start queue processor if not already running
    if (!this.queueProcessorRunning) {
      this.processLoadQueue();
    }
  }

  /**
   * Process the priority queue, loading chunks in order of priority
   * This ensures seeks are prioritized over background preloads
   */
  private async processLoadQueue(): Promise<void> {
    if (this.queueProcessorRunning) return;
    this.queueProcessorRunning = true;

    // Ensure AudioContext is initialized before decoding
    this.ensureAudioContext();

    try {
      while (this.loadQueue.getSize() > 0) {
        const nextItem = this.loadQueue.dequeue();
        if (!nextItem) break;

        const { chunkIndex, priority } = nextItem;

        // Skip if already loaded or currently loading
        const chunk = this.chunks[chunkIndex];
        if (chunk.isLoaded && chunk.audioBuffer) continue;
        if (chunk.isLoading) continue;

        // Mark as loading
        chunk.isLoading = true;
        this.debug(`[P${priority}] Loading chunk ${chunkIndex}/${this.chunks.length}`);

        try {
          // Check buffer cache first
          const cacheKey = this.buffer.getCacheKey(
            this.trackId!,
            chunkIndex,
            this.config.enhanced,
            this.config.preset
          );

          let audioBuffer = this.buffer.get(cacheKey);

          if (!audioBuffer) {
            // Fetch WebM chunk from endpoint
            const chunkUrl = `${this.config.apiBaseUrl}/api/stream/${this.trackId}/chunk/${chunkIndex}` +
              `?enhanced=${this.config.enhanced}&preset=${this.config.preset}&intensity=${this.config.intensity}`;

            const response = await fetch(chunkUrl);
            if (!response.ok) {
              throw new Error(`Failed to fetch chunk ${chunkIndex}: ${response.statusText}`);
            }

            const cacheHeader = response.headers.get('X-Cache-Tier');
            this.debug(`[P${priority}] Chunk ${chunkIndex} cache: ${cacheHeader}`);

            const arrayBuffer = await response.arrayBuffer();

            if (arrayBuffer.byteLength === 0) {
              throw new Error(`Chunk ${chunkIndex} returned empty data (0 bytes)`);
            }

            this.debug(`[P${priority}] Decoding ${arrayBuffer.byteLength} bytes for chunk ${chunkIndex}...`);

            // Decode WebM/Opus to AudioBuffer using Web Audio API
            try {
              audioBuffer = await this.audioContext!.decodeAudioData(arrayBuffer);
            } catch (decodeError: any) {
              throw new Error(`Failed to decode chunk ${chunkIndex}: ${decodeError.message || 'Unknown decode error'}`);
            }

            // Cache decoded buffer
            this.buffer.set(cacheKey, audioBuffer);
          } else {
            this.debug(`[P${priority}] Chunk ${chunkIndex} from buffer cache`);
          }

          chunk.audioBuffer = audioBuffer;
          chunk.isLoaded = true;
          chunk.isLoading = false;

          this.debug(`[P${priority}] Chunk ${chunkIndex} ready (${audioBuffer.duration.toFixed(2)}s)`);

          // Queue next chunks for background preload with lower priority
          if (priority <= 2) {
            // If this was a high-priority chunk, queue the next chunks
            for (let i = 1; i <= this.config.preloadChunks; i++) {
              const nextIdx = chunkIndex + i;
              if (nextIdx < this.chunks.length && !this.loadQueue.isQueued(nextIdx)) {
                this.loadQueue.enqueue(nextIdx, 4); // Background priority
              }
            }
          }

        } catch (error: any) {
          chunk.isLoading = false;
          chunk.audioBuffer = null; // Clear any partial state
          this.debug(`[P${priority}] Error loading chunk ${chunkIndex}: ${error.message}`);
          // Mark as failed so we know not to retry this chunk in the same queue cycle
          // but it can be retried in a future queue cycle if requested
          this.emit('chunk-error', { chunkIndex, error });
          // Continue processing next items in queue
        }
      }
    } finally {
      this.queueProcessorRunning = false;
    }
  }

  /**
   * Play from current position
   */
  async play(): Promise<void> {
    if (!this.trackId || !this.metadata) {
      throw new Error('No track loaded');
    }

    // Ensure AudioContext is initialized (required by browser autoplay policy)
    this.ensureAudioContext();

    // Resume AudioContext if suspended (browser autoplay policy)
    if (this.audioContext!.state === 'suspended') {
      await this.audioContext!.resume();
    }

    // Calculate chunk to play based on current time
    const currentTime = this.pauseTime || 0;
    const chunkInterval = this.metadata?.chunk_interval || this.metadata?.chunk_duration || 10; // Use interval for indexing
    const chunkDuration = this.metadata?.chunk_duration || 10;

    // Calculate which chunk to play (based on INTERVAL, not duration)
    // With 15s chunks and 10s intervals:
    //   0-10s: chunk 0 (plays 0-15s of audio, offset 0-10s)
    //   10-20s: chunk 1 (plays 10-25s of audio, offset 0-10s within chunk)
    //   20-30s: chunk 2 (plays 20-35s of audio, offset 0-10s within chunk)
    const chunkIndex = Math.floor(currentTime / chunkInterval);

    // Calculate offset within the chunk
    // For overlap model: offset is relative to chunk start (chunkIndex * interval)
    const chunkStartTime = chunkIndex * chunkInterval;
    const offsetInChunk = currentTime - chunkStartTime;

    // Ensure chunk is loaded
    const chunk = this.chunks[chunkIndex];
    if (!chunk.isLoaded) {
      this.setState('buffering');
      await this.preloadChunk(chunkIndex);
    }

    // Play chunk with correct offset
    await this.playChunk(chunkIndex, offsetInChunk);
  }

  /**
   * Play a specific chunk with optional offset
   *
   * CRITICAL TIMING FIX (Phase 2):
   * ==============================
   * Issue: Chunks have overlaps but timing was misaligned causing jumps/skips
   *
   * Backend architecture:
   * - Chunk 0: 15s of audio, plays during 0-10s of track
   * - Chunk 1: 15s of audio (first 5s overlaps with chunk 0), plays during 10-20s of track
   * - Chunk 2: 15s of audio (first 5s overlaps with chunk 1), plays during 20-30s of track
   *
   * Frontend fixes:
   * 1. actualBufferOffset = offset + overlap_duration (for chunks > 0)
   *    Because the first 5s of the buffer is overlap context, we skip it
   * 2. playDuration clamped to actual AudioBuffer duration
   *    Prevents trying to play more than exists in decoded buffer
   * 3. Metadata includes chunk_playable_duration and overlap_duration
   *    Frontend knows exact structure: 15s buffer = 5s overlap + 10s playable
   *
   * With 15s chunks delivered every 10s:
   * - Each chunk contains 15 seconds of overlapped audio from the backend
   * - We play only the INTERVAL duration (10s) that's "new" relative to playback timeline
   * - Backend handles overlap mixing, frontend just plays sequentially
   * - Next chunk starts automatically via onended callback when current chunk finishes
   */
  private async playChunk(chunkIndex: number, offset: number = 0): Promise<void> {
    // Ensure AudioContext is initialized (required by browser autoplay policy)
    this.ensureAudioContext();

    const chunk = this.chunks[chunkIndex];
    if (!chunk.audioBuffer) {
      // Try to reload the chunk with high priority
      this.debug(`Chunk ${chunkIndex} audioBuffer is null, attempting to reload...`);

      // Mark as not loading so preloadChunk will queue it
      chunk.isLoading = false;
      chunk.isLoaded = false;

      try {
        // Queue with CRITICAL priority (0) - this chunk is needed immediately
        this.preloadChunk(chunkIndex, 0);

        // Wait for the chunk to load (with timeout)
        const maxWaitTime = 10000; // 10 seconds
        const startTime = Date.now();
        while (!chunk.isLoaded && Date.now() - startTime < maxWaitTime) {
          await new Promise(resolve => setTimeout(resolve, 50));
        }

        if (!chunk.audioBuffer) {
          throw new Error(`Chunk ${chunkIndex} failed to load within timeout`);
        }
      } catch (error: any) {
        this.debug(`Failed to load chunk ${chunkIndex}: ${error.message}`);
        this.setState('error');
        this.emit('error', error);
        throw new Error(`Chunk ${chunkIndex} not loaded: ${error.message}`);
      }
    }

    const chunkInterval = this.metadata?.chunk_interval || this.metadata?.chunk_duration || 10;
    const chunkDuration = this.metadata?.chunk_duration || 10;

    // Stop previous source
    if (this.currentSource) {
      this.currentSource.stop();
      this.currentSource.disconnect();
    }

    // Create gain node (no crossfading, just volume control)
    const chunkGainNode = this.audioContext!.createGain();
    chunkGainNode.connect(this.gainNode!);
    chunkGainNode.gain.value = this.volume;

    // Create new buffer source
    const source = this.audioContext!.createBufferSource();
    source.buffer = chunk.audioBuffer;
    source.connect(chunkGainNode);

    // Track when this chunk started playing in audio context time
    // startTime is when source.start() is called, which is NOW
    // currentChunkOffset is where we start in the buffer (for seeking)
    this.startTime = this.audioContext!.currentTime;
    this.currentChunkIndex = chunkIndex;
    this.currentChunkOffset = offset;

    // Backend architecture: 15s chunks every 10s for smooth blending
    // Each chunk contains 15s of audio (with 5s overlap from previous chunk)
    // They are meant to be played SEQUENTIALLY, not overlapped in real time
    //
    // Chunk 0: Play 0-15s (10s for timeline, 5s extra for blending context)
    // Chunk 1: Play 0-15s (10s for timeline, 5s extra for blending context)
    // Chunk 2: Play 0-15s (10s for timeline, 5s extra for blending context)
    //
    // But wait - if backend trimmed the overlap, chunks should only be ~10s each

    const actualBufferDuration = chunk.audioBuffer!.duration;
    const isLastChunk = chunkIndex + 1 >= this.chunks.length;
    const chunkStartTime = chunkIndex * chunkInterval;
    const chunkDurationValue = this.metadata?.chunk_duration || 10;
    const overlapDuration = chunkDurationValue - chunkInterval; // Overlap with next chunk (5s for 15s chunk, 10s interval)

    let bufferOffset = offset;  // Start position in buffer
    let playDuration: number;

    if (offset > 0) {
      // Seeking within chunk - play from seek point to end of buffer
      playDuration = Math.max(0, actualBufferDuration - bufferOffset);
    } else if (isLastChunk) {
      // Last chunk - play only what's needed to reach track end
      const remainingTrack = Math.max(0, this.metadata!.duration - chunkStartTime);
      playDuration = Math.min(actualBufferDuration, remainingTrack);
    } else {
      // Normal chunk - play the FULL chunk duration to enable crossfading
      // Chunks are 15s but only 10s "new" content; the 5s overlap will be crossfaded
      // with the next chunk's beginning for smooth blending
      playDuration = Math.min(actualBufferDuration, chunkDurationValue);
    }

    // Safety: never exceed buffer
    playDuration = Math.min(playDuration, actualBufferDuration - bufferOffset);

    if (playDuration <= 0) {
      this.debug(`WARNING: Chunk ${chunkIndex} invalid duration (buffer=${actualBufferDuration.toFixed(2)}s, offset=${bufferOffset.toFixed(2)}s)`);
      playDuration = 0.1;
    }

    // DEBUG: Log chunk timing for first few chunks
    if (chunkIndex < 5) {
      this.debug(`[TIMING] Chunk ${chunkIndex}: buffer=${actualBufferDuration.toFixed(2)}s, offset=${bufferOffset.toFixed(2)}s, duration=${playDuration.toFixed(2)}s, overlap=${overlapDuration.toFixed(2)}s`);
    }

    // Queue next chunk with IMMEDIATE priority for continuous playback
    // This ensures next chunk loads before playback ends, but after seek targets
    if (chunkIndex + 1 < this.chunks.length) {
      const nextChunk = this.chunks[chunkIndex + 1];
      if (!nextChunk.isLoaded && !nextChunk.isLoading) {
        this.preloadChunk(chunkIndex + 1, 1); // IMMEDIATE priority for continuous playback
      }
    }

    // Play chunk: start from buffer offset, play for calculated duration
    // bufferOffset is where we start in the buffer (normally 0, or after seeking)
    source.start(0, bufferOffset, playDuration);

    // Keep reference to current source
    this.currentSource = source;

    // Variable to track if we've already scheduled the next chunk
    let nextChunkScheduled = false;
    let fadeTimeoutId: number | null = null;

    // CROSSFADING LOGIC: If this is not the last chunk, schedule next chunk to start
    // during the overlap region for smooth crossfading
    if (!isLastChunk && offset === 0) {
      // Schedule the next chunk to start at: (playDuration - overlapDuration)
      // This means the next chunk begins DURING the last 5s of this chunk,
      // creating a 5s window for crossfading
      const fadeStartTime = Math.max(0, playDuration - overlapDuration);

      if (fadeStartTime > 0) {
        // Use a timeout to start the next chunk at the right time
        const scheduleNextChunk = async () => {
          if (this.state === 'playing' && this.currentSource === source && !nextChunkScheduled) {
            nextChunkScheduled = true;
            try {
              this.debug(`[FADE] Starting next chunk (${chunkIndex + 1}) for crossfading`);
              await this.playChunk(chunkIndex + 1, 0);
            } catch (error: any) {
              this.debug(`Error scheduling next chunk: ${error.message}`);
            }
          }
        };

        const delayMs = fadeStartTime * 1000;
        this.debug(`Scheduling next chunk (${chunkIndex + 1}) to start in ${delayMs.toFixed(0)}ms for crossfading`);

        fadeTimeoutId = window.setTimeout(scheduleNextChunk, delayMs);
      }
    }

    // Handle end of playback - cleanup and handle last chunk
    source.onended = async () => {
      source.disconnect();
      chunkGainNode.disconnect();

      // Clear scheduled timeout if it hasn't fired yet
      if (fadeTimeoutId !== null) {
        clearTimeout(fadeTimeoutId);
      }

      // If not the last chunk AND we haven't scheduled next chunk yet, play it now
      // (This handles case where chunk ends before fade-in time)
      if (!isLastChunk && this.state === 'playing' && this.currentChunkIndex === chunkIndex && !nextChunkScheduled) {
        try {
          nextChunkScheduled = true;
          this.debug(`Playing next chunk ${chunkIndex + 1} on source ended`);
          await this.playChunk(chunkIndex + 1, 0);
        } catch (error: any) {
          this.debug(`Error playing next chunk: ${error.message}`);
          this.setState('error');
          this.emit('error', error);
        }
      } else if (isLastChunk && this.state === 'playing') {
        // Last chunk ended
        this.setState('idle');
        this.emit('ended');
      }
    };

    this.setState('playing');
    this.debug(`Playing chunk ${chunkIndex} (offset ${offset.toFixed(2)}s, duration ${playDuration.toFixed(2)}s, fade_start=${!isLastChunk ? (playDuration - overlapDuration).toFixed(2) : 'N/A'}s)`);

    // Start time updates
    this.startTimeUpdates();
  }


  /**
   * Pause playback
   */
  pause(): void {
    if (this.state !== 'playing') return;

    // Calculate current position
    this.pauseTime = this.getCurrentTime();

    // Stop playback
    if (this.currentSource) {
      this.currentSource.stop();
      this.currentSource.disconnect();
      this.currentSource = null;
    }

    this.setState('paused');
    this.stopTimeUpdates();
    this.debug(`Paused at ${this.pauseTime.toFixed(2)}s`);
  }

  /**
   * Stop playback and reset
   */
  stop(): void {
    if (this.currentSource) {
      this.currentSource.stop();
      this.currentSource.disconnect();
      this.currentSource = null;
    }

    this.pauseTime = 0;
    this.startTime = 0;
    this.currentChunkIndex = 0;

    this.setState('idle');
    this.stopTimeUpdates();
  }

  /**
   * Seek to specific time
   * HIGH PRIORITY: SEEK_TARGET (2) ensures target chunk loads before background preloads
   */
  async seek(time: number): Promise<void> {
    if (!this.metadata) throw new Error('No track loaded');

    const wasPlaying = this.state === 'playing';

    // Stop current playback
    if (this.currentSource) {
      this.currentSource.stop();
      this.currentSource.disconnect();
      this.currentSource = null;
    }

    // Calculate target chunk using chunk_interval (not duration)
    const chunkInterval = this.metadata?.chunk_interval || this.metadata?.chunk_duration || 10;
    const targetChunk = Math.floor(time / chunkInterval);

    // Calculate offset within the chunk (relative to chunk start time)
    const chunkStartTime = targetChunk * chunkInterval;
    const offset = time - chunkStartTime;

    this.debug(`Seeking to ${time.toFixed(2)}s (chunk ${targetChunk}, offset ${offset.toFixed(2)}s)`);

    // Queue target chunk with high priority (SEEK_TARGET = 2)
    // This interrupts background preloads to prioritize the seek position
    const chunk = this.chunks[targetChunk];
    if (!chunk.isLoaded) {
      this.setState('buffering');
      this.preloadChunk(targetChunk, 2); // SEEK_TARGET priority

      // Also queue adjacent chunks for smoother playback
      if (targetChunk > 0) {
        this.preloadChunk(targetChunk - 1, 3); // ADJACENT priority
      }
      if (targetChunk + 1 < this.chunks.length) {
        this.preloadChunk(targetChunk + 1, 3); // ADJACENT priority
      }

      // Wait for target chunk to be loaded
      await new Promise<void>((resolve) => {
        const checkLoaded = () => {
          if (chunk.isLoaded && chunk.audioBuffer) {
            resolve();
          } else {
            // Check again in 50ms
            setTimeout(checkLoaded, 50);
          }
        };
        checkLoaded();
      });
    }

    // Update position
    this.pauseTime = time;

    // Resume playback if was playing
    if (wasPlaying) {
      await this.playChunk(targetChunk, offset);
    }
  }

  /**
   * Set enhancement mode (triggers buffer flush and reload)
   *
   * NEW (Beta.9 Phase 2): Improved toggle with instant buffer flush
   * - Saves playback position
   * - Stops current playback
   * - Clears buffer completely
   * - Reloads from current position with new settings
   * - Resumes playback if was playing
   */
  async setEnhanced(enabled: boolean, preset?: string): Promise<void> {
    const oldEnhanced = this.config.enhanced;
    const oldPreset = this.config.preset;

    this.config.enhanced = enabled;
    if (preset) this.config.preset = preset;

    // If settings changed, flush buffer and reload
    if (oldEnhanced !== enabled || (preset && oldPreset !== preset)) {
      this.debug(`Enhancement changed: ${enabled}, preset: ${preset || this.config.preset}`);

      // NEW (Beta.9): Save playback state
      const wasPlaying = this.state === 'playing';
      const currentTime = this.getCurrentTime();

      // Stop current playback (releases audio buffers)
      if (this.currentSource) {
        this.currentSource.stop();
        this.currentSource.disconnect();
        this.currentSource = null;
      }

      // Clear buffer completely (releases cached chunks)
      this.buffer.clear();

      this.debug(`Buffer flushed at ${currentTime.toFixed(2)}s, wasPlaying: ${wasPlaying}`);

      // Reload from current position
      if (this.trackId && this.currentChunkIndex < this.chunks.length) {
        // Preload current chunk AND next chunk in parallel to avoid blocking
        // This prevents the event loop from being blocked and keeps backend responsive
        const preloadPromises = [this.preloadChunk(this.currentChunkIndex)];

        if (this.currentChunkIndex + 1 < this.chunks.length) {
          preloadPromises.push(this.preloadChunk(this.currentChunkIndex + 1));
        }

        // Wait for both chunks to load in parallel
        await Promise.all(preloadPromises);
        this.debug(`Preloaded ${preloadPromises.length} chunk(s) in parallel for smooth enhancement toggle`);

        // Resume playback if was playing
        if (wasPlaying) {
          this.debug(`Resuming playback from ${currentTime.toFixed(2)}s with new settings`);
          await this.seek(currentTime);
          await this.play();
        }
      }
    }
  }

  /**
   * Set preset (triggers chunk reload)
   */
  async setPreset(preset: string): Promise<void> {
    await this.setEnhanced(this.config.enhanced, preset);
  }

  /**
   * Set volume (0.0 - 1.0)
   */
  setVolume(volume: number): void {
    this.volume = Math.max(0, Math.min(1, volume));
    if (this.gainNode) {
      this.gainNode.gain.value = this.volume;
    }
  }

  /**
   * Get current playback time
   *
   * Timeline position calculation:
   * =============================
   * We play only the primary 10s interval of each chunk:
   * - Chunk 0: Play 0-10s (buffer has 15s total, but we play first 10s)
   * - Chunk 1: Play 10-20s (buffer has 15s total, but we play first 10s)
   * - Chunk 2: Play 20-30s (buffer has 15s total, but we play first 10s)
   *
   * The backend pre-mixed the 5s blend context into each chunk's audio.
   * We only play the primary interval to avoid timeline jumps and repeated audio.
   *
   * Timeline position = (chunkIndex × 10s) + elapsed_since_chunk_start
   * Clamped to next chunk's start time to prevent blend context from extending past interval
   */
  getCurrentTime(): number {
    if (this.state === 'playing' && this.currentSource && this.audioContext) {
      const chunkInterval = this.metadata?.chunk_interval || 10;

      // Timeline position where this chunk starts (0s, 10s, 20s, 30s, etc.)
      const chunkStartTime = this.currentChunkIndex * chunkInterval;

      // Elapsed time since this chunk started playing (in seconds)
      const elapsedInChunk = this.audioContext.currentTime - this.startTime;

      // Current track timeline position
      let currentTime = chunkStartTime + this.currentChunkOffset + elapsedInChunk;

      // Clamp to interval boundaries to prevent playback from extending past next chunk
      const isLastChunk = this.currentChunkIndex + 1 >= this.chunks.length;
      if (!isLastChunk) {
        // Can't go past the start of the next chunk
        const nextChunkStart = (this.currentChunkIndex + 1) * chunkInterval;
        currentTime = Math.min(currentTime, nextChunkStart);
      } else {
        // Last chunk: can't go past track duration
        currentTime = Math.min(currentTime, this.metadata!.duration);
      }

      return currentTime;
    }
    return this.pauseTime;
  }

  /**
   * Get track duration
   */
  getDuration(): number {
    return this.metadata?.duration || 0;
  }

  /**
   * Get current state
   */
  getState(): PlaybackState {
    return this.state;
  }

  /**
   * Get metadata
   */
  getMetadata(): StreamMetadata | null {
    return this.metadata;
  }

  /**
   * Cleanup resources
   */
  cleanup(): void {
    this.stop();
    this.buffer.clear();
    if (this.audioContext) {
      this.audioContext.close();
    }
    this.listeners.clear();
  }

  // ========================================
  // Event System
  // ========================================

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

  private emit(event: string, data?: any): void {
    this.listeners.get(event)?.forEach(callback => callback(data));
  }

  // ========================================
  // Internal Helpers
  // ========================================

  private setState(newState: PlaybackState): void {
    if (this.state !== newState) {
      const oldState = this.state;
      this.state = newState;
      this.debug(`State: ${oldState} → ${newState}`);
      this.emit('statechange', { oldState, newState });
    }
  }

  private timeUpdateInterval: number | null = null;

  private startTimeUpdates(): void {
    if (this.timeUpdateInterval) return;

    this.timeUpdateInterval = window.setInterval(() => {
      if (this.state === 'playing') {
        const currentTime = this.getCurrentTime();
        const duration = this.getDuration();
        this.emit('timeupdate', { currentTime, duration });
      }
    }, 100); // Update every 100ms
  }

  private stopTimeUpdates(): void {
    if (this.timeUpdateInterval) {
      clearInterval(this.timeUpdateInterval);
      this.timeUpdateInterval = null;
    }
  }

  private debug(message: string): void {
    if (this.config.debug) {
      console.log(`[UnifiedWebMAudioPlayer] ${message}`);
    }
  }
}

export default UnifiedWebMAudioPlayer;
