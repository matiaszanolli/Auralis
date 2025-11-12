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
  private audioContext: AudioContext;
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
  private pauseTime: number = 0;
  private volume: number = 1.0;

  // Gain node for volume control
  private gainNode: GainNode;

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

    // Initialize Web Audio API
    this.audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
    this.gainNode = this.audioContext.createGain();
    this.gainNode.connect(this.audioContext.destination);

    // Initialize buffer
    this.buffer = new MultiTierWebMBuffer();

    // Initialize priority queue
    this.loadQueue = new ChunkLoadPriorityQueue();

    this.debug('UnifiedWebMAudioPlayer initialized');
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

      this.metadata = await response.json();
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
              audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);
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

    // Resume AudioContext if suspended (browser autoplay policy)
    if (this.audioContext.state === 'suspended') {
      await this.audioContext.resume();
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
   * With 15s chunks delivered every 10s:
   * - Each chunk contains 15 seconds of overlapped audio from the backend
   * - We play only the INTERVAL duration (10s) that's "new" relative to playback timeline
   * - Backend handles overlap mixing, frontend just plays sequentially
   * - Next chunk starts automatically via onended callback when current chunk finishes
   */
  private async playChunk(chunkIndex: number, offset: number = 0): Promise<void> {
    const chunk = this.chunks[chunkIndex];
    if (!chunk.audioBuffer) {
      // Instead of throwing immediately, try to reload the chunk
      this.debug(`Chunk ${chunkIndex} audioBuffer is null, attempting to reload...`);
      try {
        await this.preloadChunk(chunkIndex);
        if (!this.chunks[chunkIndex].audioBuffer) {
          throw new Error(`Chunk ${chunkIndex} failed to load and has no audio buffer`);
        }
      } catch (error: any) {
        this.debug(`Failed to load chunk ${chunkIndex}: ${error.message}`);
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
    const chunkGainNode = this.audioContext.createGain();
    chunkGainNode.connect(this.gainNode);
    chunkGainNode.gain.value = this.volume;

    // Create new buffer source
    const source = this.audioContext.createBufferSource();
    source.buffer = chunk.audioBuffer;
    source.connect(chunkGainNode);

    // Track when playback started
    this.startTime = this.audioContext.currentTime - offset;
    this.currentChunkIndex = chunkIndex;

    // Calculate play duration based on position in track
    // First chunk plays full interval (0-10s of audio)
    // Subsequent chunks also play interval duration (10-20s, 20-30s, etc.)
    const isLastChunk = chunkIndex + 1 >= this.chunks.length;
    const chunkStartTime = chunkIndex * chunkInterval;
    const chunkEndTime = Math.min((chunkIndex + 1) * chunkInterval, this.metadata!.duration);
    const playDuration = Math.max(0, chunkEndTime - chunkStartTime - offset);

    // Buffer offset: if seeking within chunk, skip ahead
    const bufferOffset = offset;

    // Queue next chunk with IMMEDIATE priority for continuous playback
    // This ensures next chunk loads before playback ends, but after seek targets
    if (chunkIndex + 1 < this.chunks.length) {
      const nextChunk = this.chunks[chunkIndex + 1];
      if (!nextChunk.isLoaded && !nextChunk.isLoading) {
        this.preloadChunk(chunkIndex + 1, 1); // IMMEDIATE priority for continuous playback
      }
    }

    // Handle end of playback
    source.onended = async () => {
      source.disconnect();
      chunkGainNode.disconnect();

      // If not the last chunk, automatically play next chunk
      if (!isLastChunk && this.state === 'playing' && this.currentChunkIndex === chunkIndex) {
        try {
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

    // Play chunk: start from buffer offset, play for calculated duration
    // For normal playback: bufferOffset=0, playDuration=10s
    // For seeking within a chunk: bufferOffset=position, playDuration=remaining
    source.start(0, bufferOffset, playDuration);

    // Keep reference to current source
    this.currentSource = source;

    this.setState('playing');
    this.debug(`Playing chunk ${chunkIndex} (offset ${offset.toFixed(2)}s, duration ${playDuration.toFixed(2)}s)`);

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
    this.gainNode.gain.value = this.volume;
  }

  /**
   * Get current playback time
   */
  getCurrentTime(): number {
    if (this.state === 'playing' && this.currentSource) {
      // Get time within current chunk
      const timeInCurrentChunk = this.audioContext.currentTime - this.startTime;

      // Get accumulated time from all previous chunks
      const accumulatedTime = this.currentChunkIndex >= 0 && this.chunks[this.currentChunkIndex]
        ? this.chunks[this.currentChunkIndex].startTime
        : 0;

      // Return total time (accumulated + current chunk)
      return accumulatedTime + timeInCurrentChunk;
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
    this.audioContext.close();
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
