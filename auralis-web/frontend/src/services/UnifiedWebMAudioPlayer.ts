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
  chunk_duration: number;
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
 * Unified WebM Audio Player
 * Uses Web Audio API for all playback
 */
export class UnifiedWebMAudioPlayer {
  private config: Required<UnifiedWebMAudioPlayerConfig>;
  private audioContext: AudioContext;
  private buffer: MultiTierWebMBuffer;

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
      this.chunks = [];
      for (let i = 0; i < this.metadata.total_chunks; i++) {
        this.chunks.push({
          index: i,
          startTime: i * this.metadata.chunk_duration,
          endTime: Math.min((i + 1) * this.metadata.chunk_duration, this.metadata.duration),
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
   */
  private async preloadChunk(chunkIndex: number): Promise<void> {
    if (chunkIndex >= this.chunks.length) return;

    const chunk = this.chunks[chunkIndex];
    if (chunk.isLoaded || chunk.isLoading) return;

    chunk.isLoading = true;
    this.debug(`Preloading chunk ${chunkIndex}/${this.chunks.length}`);

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
        // Fetch WebM chunk from NEW endpoint
        const chunkUrl = `${this.config.apiBaseUrl}/api/stream/${this.trackId}/chunk/${chunkIndex}` +
          `?enhanced=${this.config.enhanced}&preset=${this.config.preset}&intensity=${this.config.intensity}`;

        const response = await fetch(chunkUrl);
        if (!response.ok) {
          throw new Error(`Failed to fetch chunk ${chunkIndex}: ${response.statusText}`);
        }

        const cacheHeader = response.headers.get('X-Cache-Tier');
        this.debug(`Chunk ${chunkIndex} cache: ${cacheHeader}`);

        const arrayBuffer = await response.arrayBuffer();

        // Decode WebM/Opus to AudioBuffer using Web Audio API
        audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);

        // Cache decoded buffer
        this.buffer.set(cacheKey, audioBuffer);
      } else {
        this.debug(`Chunk ${chunkIndex} from buffer cache`);
      }

      chunk.audioBuffer = audioBuffer;
      chunk.isLoaded = true;
      chunk.isLoading = false;

      this.debug(`Chunk ${chunkIndex} ready (${audioBuffer.duration.toFixed(2)}s)`);

      // Preload next chunks
      for (let i = 1; i <= this.config.preloadChunks; i++) {
        const nextIdx = chunkIndex + i;
        if (nextIdx < this.chunks.length) {
          this.preloadChunk(nextIdx); // Fire and forget
        }
      }

    } catch (error: any) {
      chunk.isLoading = false;
      this.debug(`Error preloading chunk ${chunkIndex}: ${error.message}`);
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

    // Resume AudioContext if suspended (browser autoplay policy)
    if (this.audioContext.state === 'suspended') {
      await this.audioContext.resume();
    }

    // Calculate chunk to play based on current time
    const currentTime = this.pauseTime || 0;
    const chunkDuration = this.metadata?.chunk_duration || 10; // Fallback only if metadata not loaded
    const chunkIndex = Math.floor(currentTime / chunkDuration);

    // Ensure chunk is loaded
    const chunk = this.chunks[chunkIndex];
    if (!chunk.isLoaded) {
      this.setState('buffering');
      await this.preloadChunk(chunkIndex);
    }

    // Play chunk
    await this.playChunk(chunkIndex, currentTime % chunkDuration);
  }

  /**
   * Play a specific chunk with optional offset
   */
  private async playChunk(chunkIndex: number, offset: number = 0): Promise<void> {
    const chunk = this.chunks[chunkIndex];
    if (!chunk.audioBuffer) {
      throw new Error(`Chunk ${chunkIndex} not loaded`);
    }

    // Stop current playback
    if (this.currentSource) {
      this.currentSource.stop();
      this.currentSource.disconnect();
    }

    // Create new buffer source
    this.currentSource = this.audioContext.createBufferSource();
    this.currentSource.buffer = chunk.audioBuffer;
    this.currentSource.connect(this.gainNode);

    // Set volume
    this.gainNode.gain.value = this.volume;

    // Track when playback started
    this.startTime = this.audioContext.currentTime - offset;
    this.currentChunkIndex = chunkIndex;

    // When chunk ends, play next chunk
    this.currentSource.onended = () => {
      if (this.state === 'playing') {
        const nextIdx = chunkIndex + 1;
        if (nextIdx < this.chunks.length) {
          this.playChunk(nextIdx, 0); // Play next chunk from start
        } else {
          // Track ended
          this.setState('idle');
          this.emit('ended');
        }
      }
    };

    // Start playback with offset
    this.currentSource.start(0, offset);

    this.setState('playing');
    this.debug(`Playing chunk ${chunkIndex} from ${offset.toFixed(2)}s`);

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

    // Calculate target chunk using backend-provided chunk_duration
    const chunkDuration = this.metadata?.chunk_duration || 10; // Fallback only if metadata not loaded
    const targetChunk = Math.floor(time / chunkDuration);
    const offset = time % chunkDuration;

    this.debug(`Seeking to ${time.toFixed(2)}s (chunk ${targetChunk}, offset ${offset.toFixed(2)}s)`);

    // Ensure chunk is loaded
    const chunk = this.chunks[targetChunk];
    if (!chunk.isLoaded) {
      this.setState('buffering');
      await this.preloadChunk(targetChunk);
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
        // Preload current chunk with new settings
        await this.preloadChunk(this.currentChunkIndex);

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
