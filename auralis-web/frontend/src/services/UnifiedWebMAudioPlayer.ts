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
   * Play a specific chunk with optional offset and crossfade
   *
   * With 15s chunks every 10s:
   * - Chunk plays for INTERVAL duration (10s), not full DURATION (15s)
   * - Next chunk starts with 5s crossfade during overlap region
   * - Crossfade uses exponential volume curves for natural transition
   */
  private async playChunk(chunkIndex: number, offset: number = 0): Promise<void> {
    const chunk = this.chunks[chunkIndex];
    if (!chunk.audioBuffer) {
      throw new Error(`Chunk ${chunkIndex} not loaded`);
    }

    const chunkInterval = this.metadata?.chunk_interval || this.metadata?.chunk_duration || 10;
    const chunkDuration = this.metadata?.chunk_duration || 10;
    const crossfadeDuration = chunkDuration - chunkInterval; // 5s

    // Stop previous source (if not crossfading)
    if (this.currentSource && offset > 0) {
      this.currentSource.stop();
      this.currentSource.disconnect();
    }

    // Create gain node for this chunk (for crossfade control)
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

    // Calculate when to start next chunk for crossfade
    // Play current chunk for (interval - offset) seconds
    const playDuration = chunkInterval - offset;
    const crossfadeStartTime = this.audioContext.currentTime + playDuration - crossfadeDuration;

    // Schedule crossfade and next chunk
    if (chunkIndex + 1 < this.chunks.length) {
      // Ensure next chunk is loaded
      const nextChunk = this.chunks[chunkIndex + 1];
      if (!nextChunk.isLoaded) {
        this.preloadChunk(chunkIndex + 1); // Start loading
      }

      // Schedule fade out of current chunk
      setTimeout(async () => {
        if (this.state === 'playing' && this.currentChunkIndex === chunkIndex) {
          // Start fade out (exponential curve for natural sound)
          const now = this.audioContext.currentTime;
          chunkGainNode.gain.setValueAtTime(this.volume, now);
          chunkGainNode.gain.exponentialRampToValueAtTime(0.01, now + crossfadeDuration);

          // Start next chunk with fade in
          await this.playChunkWithCrossfade(chunkIndex + 1);
        }
      }, (playDuration - crossfadeDuration) * 1000);

      // When chunk interval ends, current source can stop
      source.onended = () => {
        source.disconnect();
        chunkGainNode.disconnect();
      };
    } else {
      // Last chunk - no crossfade, just end
      source.onended = () => {
        source.disconnect();
        chunkGainNode.disconnect();
        if (this.state === 'playing') {
          this.setState('idle');
          this.emit('ended');
        }
      };
    }

    // Start playback with offset
    // Play only the interval duration (10s), not full chunk (15s)
    source.start(0, offset, playDuration);

    // Keep reference to current source
    this.currentSource = source;

    this.setState('playing');
    this.debug(`Playing chunk ${chunkIndex} from ${offset.toFixed(2)}s for ${playDuration.toFixed(2)}s (crossfade in ${(playDuration - crossfadeDuration).toFixed(2)}s)`);

    // Start time updates
    this.startTimeUpdates();
  }

  /**
   * Play next chunk with fade-in during crossfade
   */
  private async playChunkWithCrossfade(chunkIndex: number): Promise<void> {
    const chunk = this.chunks[chunkIndex];

    // Wait for chunk to load if needed
    if (!chunk.isLoaded) {
      await this.preloadChunk(chunkIndex);
    }

    if (!chunk.audioBuffer) {
      this.debug(`Warning: Chunk ${chunkIndex} not loaded, skipping crossfade`);
      return;
    }

    const chunkInterval = this.metadata?.chunk_interval || this.metadata?.chunk_duration || 10;
    const chunkDuration = this.metadata?.chunk_duration || 10;
    const crossfadeDuration = chunkDuration - chunkInterval; // 5s

    // Create gain node for fade in
    const chunkGainNode = this.audioContext.createGain();
    chunkGainNode.connect(this.gainNode);
    chunkGainNode.gain.value = 0.01; // Start silent

    // Create buffer source
    const source = this.audioContext.createBufferSource();
    source.buffer = chunk.audioBuffer;
    source.connect(chunkGainNode);

    // Fade in (exponential curve)
    const now = this.audioContext.currentTime;
    chunkGainNode.gain.setValueAtTime(0.01, now);
    chunkGainNode.gain.exponentialRampToValueAtTime(this.volume, now + crossfadeDuration);

    // Update tracking
    this.currentChunkIndex = chunkIndex;

    // CRITICAL: Update startTime when transitioning to new chunk!
    // Without this, getCurrentTime() uses stale startTime and causes fast-forwarding
    // startTime tracks when Web Audio started playing this chunk
    this.startTime = this.audioContext.currentTime;

    // Calculate play duration (interval duration)
    const playDuration = chunkInterval;

    // Schedule next chunk if available
    if (chunkIndex + 1 < this.chunks.length) {
      setTimeout(async () => {
        if (this.state === 'playing' && this.currentChunkIndex === chunkIndex) {
          // Fade out current and start next
          const fadeNow = this.audioContext.currentTime;
          chunkGainNode.gain.setValueAtTime(this.volume, fadeNow);
          chunkGainNode.gain.exponentialRampToValueAtTime(0.01, fadeNow + crossfadeDuration);

          await this.playChunkWithCrossfade(chunkIndex + 1);
        }
      }, (playDuration - crossfadeDuration) * 1000);
    }

    // When chunk ends, disconnect
    source.onended = () => {
      source.disconnect();
      chunkGainNode.disconnect();

      if (chunkIndex + 1 >= this.chunks.length && this.state === 'playing') {
        // Last chunk ended
        this.setState('idle');
        this.emit('ended');
      }
    };

    // Start playback from beginning, play for interval duration
    source.start(0, 0, playDuration);

    this.debug(`Crossfading to chunk ${chunkIndex} (fade in ${crossfadeDuration.toFixed(2)}s, play ${playDuration.toFixed(2)}s)`);
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

    // Calculate target chunk using chunk_interval (not duration)
    const chunkInterval = this.metadata?.chunk_interval || this.metadata?.chunk_duration || 10;
    const targetChunk = Math.floor(time / chunkInterval);

    // Calculate offset within the chunk (relative to chunk start time)
    const chunkStartTime = targetChunk * chunkInterval;
    const offset = time - chunkStartTime;

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
