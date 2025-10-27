/**
 * UnifiedPlayerManager - Unified MSE + HTML5 Audio Player Manager
 * ================================================================
 *
 * Orchestrates between two player modes:
 * 1. MSE Player (unenhanced mode) - Progressive streaming with instant preset switching
 * 2. HTML5 Audio Player (enhanced mode) - Standard playback with real-time processing
 *
 * Features:
 * - Seamless switching between enhanced/unenhanced modes
 * - Position preservation across mode transitions
 * - Unified API for both player types
 * - Automatic cleanup and resource management
 *
 * Architecture:
 * - Uses unified backend endpoint: /api/audio/stream/{track_id}/*
 * - Backend intelligently routes based on 'enhanced' parameter
 * - Single manager handles all playback logic
 *
 * @copyright (C) 2025 Auralis Team
 * @license GPLv3
 */

export interface UnifiedPlayerConfig {
  /** Backend API base URL */
  apiBaseUrl?: string;

  /** Chunk duration for MSE mode (seconds) */
  chunkDuration?: number;

  /** Enable audio enhancement */
  enhanced?: boolean;

  /** Enhancement preset (adaptive, warm, bright, etc.) */
  preset?: string;

  /** Enhancement intensity (0-1) */
  intensity?: number;

  /** Number of chunks to buffer ahead in MSE mode */
  bufferAhead?: number;

  /** Enable debug logging */
  debug?: boolean;
}

export type PlayerMode = 'mse' | 'html5';

export type PlayerState =
  | 'idle'
  | 'loading'
  | 'ready'
  | 'playing'
  | 'paused'
  | 'buffering'
  | 'switching'  // Transitioning between modes
  | 'error';

export interface StreamMetadata {
  track_id: number;
  duration: number;
  total_chunks: number;
  chunk_duration: number;
  format: string;
  enhanced: boolean;
  preset: string;
  supports_seeking: boolean;
}

export type PlayerEvent =
  | 'statechange'
  | 'timeupdate'
  | 'ended'
  | 'error'
  | 'modeswitched'
  | 'presetswitched';

type EventCallback = (data?: any) => void;

/**
 * MSE Player for unenhanced mode - progressive streaming
 */
class MSEPlayerInternal {
  private audioElement: HTMLAudioElement;
  private mediaSource: MediaSource | null = null;
  private sourceBuffer: SourceBuffer | null = null;
  private trackId: number | null = null;
  private metadata: StreamMetadata | null = null;
  private currentChunkIdx: number = 0;
  private loadedChunks: Set<number> = new Set();
  private isInitialized: boolean = false;

  constructor(
    private config: Required<UnifiedPlayerConfig>,
    private debug: (msg: string) => void
  ) {
    this.audioElement = new Audio();
    this.setupAudioElement();
  }

  private setupAudioElement(): void {
    this.audioElement.preload = 'auto';
    this.audioElement.crossOrigin = 'anonymous';
  }

  async loadTrack(trackId: number): Promise<void> {
    this.debug(`MSE: Loading track ${trackId}`);
    this.trackId = trackId;
    this.currentChunkIdx = 0;
    this.loadedChunks.clear();

    // Fetch metadata
    const metadataUrl = `${this.config.apiBaseUrl}/api/audio/stream/${trackId}/metadata?enhanced=false`;
    const response = await fetch(metadataUrl);
    if (!response.ok) throw new Error(`Failed to fetch metadata: ${response.statusText}`);

    this.metadata = await response.json();
    this.debug(`MSE: Metadata loaded, ${this.metadata.total_chunks} chunks`);

    // Initialize MediaSource
    await this.initializeMediaSource();

    // Load first chunk
    await this.loadChunk(0);
  }

  private async initializeMediaSource(): Promise<void> {
    if (!this.metadata) throw new Error('No metadata');

    return new Promise((resolve, reject) => {
      this.mediaSource = new MediaSource();
      this.audioElement.src = URL.createObjectURL(this.mediaSource);

      this.mediaSource.addEventListener('sourceopen', async () => {
        try {
          if (!this.mediaSource || !this.metadata) return;

          // Add source buffer with WebM/Opus format
          this.sourceBuffer = this.mediaSource.addSourceBuffer('audio/webm; codecs="opus"');
          this.sourceBuffer.mode = 'sequence';

          this.isInitialized = true;
          this.debug('MSE: MediaSource initialized');
          resolve();
        } catch (error) {
          reject(error);
        }
      });

      this.mediaSource.addEventListener('error', (e) => {
        reject(new Error('MediaSource error'));
      });
    });
  }

  private async loadChunk(chunkIdx: number): Promise<void> {
    if (!this.trackId || !this.metadata || !this.sourceBuffer) return;
    if (this.loadedChunks.has(chunkIdx)) return;

    const chunkUrl = `${this.config.apiBaseUrl}/api/audio/stream/${this.trackId}/chunk/${chunkIdx}?enhanced=false`;

    try {
      const response = await fetch(chunkUrl);
      if (!response.ok) throw new Error(`Failed to load chunk ${chunkIdx}`);

      const arrayBuffer = await response.arrayBuffer();

      // Wait for source buffer to be ready
      await this.waitForSourceBufferReady();

      this.sourceBuffer.appendBuffer(arrayBuffer);
      this.loadedChunks.add(chunkIdx);

      this.debug(`MSE: Loaded chunk ${chunkIdx}/${this.metadata.total_chunks}`);

      // Preload next chunk
      if (chunkIdx + 1 < this.metadata.total_chunks) {
        setTimeout(() => this.loadChunk(chunkIdx + 1), 100);
      }
    } catch (error) {
      console.error(`Failed to load chunk ${chunkIdx}:`, error);
    }
  }

  private waitForSourceBufferReady(): Promise<void> {
    if (!this.sourceBuffer) return Promise.resolve();
    if (!this.sourceBuffer.updating) return Promise.resolve();

    return new Promise((resolve) => {
      const handler = () => {
        this.sourceBuffer?.removeEventListener('updateend', handler);
        resolve();
      };
      this.sourceBuffer.addEventListener('updateend', handler);
    });
  }

  getAudioElement(): HTMLAudioElement {
    return this.audioElement;
  }

  async play(): Promise<void> {
    await this.audioElement.play();
  }

  pause(): void {
    this.audioElement.pause();
  }

  async seek(time: number): Promise<void> {
    this.audioElement.currentTime = time;
  }

  getCurrentTime(): number {
    return this.audioElement.currentTime;
  }

  getDuration(): number {
    return this.metadata?.duration ?? 0;
  }

  cleanup(): void {
    this.pause();
    this.audioElement.src = '';
    if (this.mediaSource) {
      if (this.mediaSource.readyState === 'open') {
        this.mediaSource.endOfStream();
      }
      this.mediaSource = null;
    }
    this.sourceBuffer = null;
    this.loadedChunks.clear();
    this.isInitialized = false;
  }
}

/**
 * HTML5 Audio Player for enhanced mode - standard playback
 */
class HTML5AudioPlayerInternal {
  private audioElement: HTMLAudioElement;
  private trackId: number | null = null;
  private metadata: StreamMetadata | null = null;

  constructor(
    private config: Required<UnifiedPlayerConfig>,
    private debug: (msg: string) => void
  ) {
    this.audioElement = new Audio();
    this.setupAudioElement();
  }

  private setupAudioElement(): void {
    this.audioElement.preload = 'auto';
    this.audioElement.crossOrigin = 'anonymous';
  }

  async loadTrack(trackId: number): Promise<void> {
    this.debug(`HTML5: Loading track ${trackId}`);
    this.trackId = trackId;

    // Fetch metadata
    const metadataUrl = `${this.config.apiBaseUrl}/api/audio/stream/${trackId}/metadata?enhanced=true&preset=${this.config.preset}`;
    const response = await fetch(metadataUrl);
    if (!response.ok) throw new Error(`Failed to fetch metadata: ${response.statusText}`);

    this.metadata = await response.json();
    this.debug(`HTML5: Metadata loaded, duration ${this.metadata.duration}s`);

    // For enhanced mode, we load chunk 0 which is the complete enhanced track
    const audioUrl = `${this.config.apiBaseUrl}/api/audio/stream/${trackId}/chunk/0?enhanced=true&preset=${this.config.preset}&intensity=${this.config.intensity}`;
    this.audioElement.src = audioUrl;

    // Preload
    await new Promise((resolve, reject) => {
      const onCanPlay = () => {
        this.audioElement.removeEventListener('canplay', onCanPlay);
        this.audioElement.removeEventListener('error', onError);
        resolve(undefined);
      };
      const onError = () => {
        this.audioElement.removeEventListener('canplay', onCanPlay);
        this.audioElement.removeEventListener('error', onError);
        reject(new Error('Failed to load audio'));
      };

      this.audioElement.addEventListener('canplay', onCanPlay);
      this.audioElement.addEventListener('error', onError);
      this.audioElement.load();
    });
  }

  getAudioElement(): HTMLAudioElement {
    return this.audioElement;
  }

  async play(): Promise<void> {
    await this.audioElement.play();
  }

  pause(): void {
    this.audioElement.pause();
  }

  async seek(time: number): Promise<void> {
    this.audioElement.currentTime = time;
  }

  getCurrentTime(): number {
    return this.audioElement.currentTime;
  }

  getDuration(): number {
    return this.metadata?.duration ?? 0;
  }

  cleanup(): void {
    this.pause();
    this.audioElement.src = '';
    this.trackId = null;
    this.metadata = null;
  }
}

/**
 * Unified Player Manager - Orchestrates MSE and HTML5 players
 */
export class UnifiedPlayerManager {
  private config: Required<UnifiedPlayerConfig>;
  private currentMode: PlayerMode;
  private msePlayer: MSEPlayerInternal | null = null;
  private html5Player: HTML5AudioPlayerInternal | null = null;
  private state: PlayerState = 'idle';
  private currentTrackId: number | null = null;
  private eventListeners: Map<PlayerEvent, Set<EventCallback>> = new Map();

  constructor(config: UnifiedPlayerConfig = {}) {
    this.config = {
      apiBaseUrl: config.apiBaseUrl ?? 'http://localhost:8765',
      chunkDuration: config.chunkDuration ?? 30,
      enhanced: config.enhanced ?? false,
      preset: config.preset ?? 'adaptive',
      intensity: config.intensity ?? 1.0,
      bufferAhead: config.bufferAhead ?? 2,
      debug: config.debug ?? false
    };

    this.currentMode = this.config.enhanced ? 'html5' : 'mse';
    this.debug('UnifiedPlayerManager initialized');
  }

  private debug(msg: string): void {
    if (this.config.debug) {
      console.log(`[UnifiedPlayer] ${msg}`);
    }
  }

  /**
   * Load and prepare track for playback
   */
  async loadTrack(trackId: number): Promise<void> {
    try {
      this.setState('loading');
      this.currentTrackId = trackId;

      // Clean up existing player
      if (this.msePlayer) this.msePlayer.cleanup();
      if (this.html5Player) this.html5Player.cleanup();

      // Create appropriate player based on mode
      if (this.currentMode === 'mse') {
        this.msePlayer = new MSEPlayerInternal(this.config, (msg) => this.debug(msg));
        await this.msePlayer.loadTrack(trackId);
        this.setupEventForwarding(this.msePlayer.getAudioElement());
      } else {
        this.html5Player = new HTML5AudioPlayerInternal(this.config, (msg) => this.debug(msg));
        await this.html5Player.loadTrack(trackId);
        this.setupEventForwarding(this.html5Player.getAudioElement());
      }

      this.setState('ready');
      this.debug(`Track ${trackId} loaded in ${this.currentMode} mode`);
    } catch (error) {
      this.setState('error');
      this.emit('error', error);
      throw error;
    }
  }

  /**
   * Forward audio element events to manager events
   */
  private setupEventForwarding(audio: HTMLAudioElement): void {
    audio.addEventListener('timeupdate', () => {
      this.emit('timeupdate', { currentTime: audio.currentTime, duration: audio.duration });
    });

    audio.addEventListener('ended', () => {
      this.setState('idle');
      this.emit('ended');
    });

    audio.addEventListener('error', (e) => {
      this.setState('error');
      this.emit('error', e);
    });

    audio.addEventListener('waiting', () => {
      this.setState('buffering');
    });

    audio.addEventListener('canplay', () => {
      if (this.state === 'buffering') {
        this.setState('ready');
      }
    });
  }

  /**
   * Start playback
   */
  async play(): Promise<void> {
    try {
      const player = this.getCurrentPlayer();
      if (!player) throw new Error('No player loaded');

      await player.play();
      this.setState('playing');
    } catch (error) {
      this.setState('error');
      this.emit('error', error);
      throw error;
    }
  }

  /**
   * Pause playback
   */
  pause(): void {
    const player = this.getCurrentPlayer();
    if (!player) return;

    player.pause();
    this.setState('paused');
  }

  /**
   * Seek to position
   */
  async seek(time: number): Promise<void> {
    const player = this.getCurrentPlayer();
    if (!player) return;

    await player.seek(time);
  }

  /**
   * Switch between enhanced/unenhanced modes
   */
  async setEnhanced(enhanced: boolean, preset?: string): Promise<void> {
    if (this.config.enhanced === enhanced && (!preset || this.config.preset === preset)) {
      return; // No change needed
    }

    const wasPlaying = this.state === 'playing';
    const currentTime = this.getCurrentTime();

    this.debug(`Switching mode: enhanced=${enhanced}, preset=${preset ?? this.config.preset}`);
    this.setState('switching');

    // Update config
    this.config.enhanced = enhanced;
    if (preset) this.config.preset = preset;
    this.currentMode = enhanced ? 'html5' : 'mse';

    // Reload track in new mode
    if (this.currentTrackId !== null) {
      await this.loadTrack(this.currentTrackId);

      // Restore position
      await this.seek(currentTime);

      // Resume playback if was playing
      if (wasPlaying) {
        await this.play();
      }
    }

    this.emit('modeswitched', { mode: this.currentMode, enhanced });
    this.debug(`Mode switched to ${this.currentMode}`);
  }

  /**
   * Change preset (only affects enhanced mode)
   */
  async setPreset(preset: string): Promise<void> {
    if (!this.config.enhanced) {
      // If not enhanced, just update config
      this.config.preset = preset;
      return;
    }

    await this.setEnhanced(true, preset);
    this.emit('presetswitched', { preset });
  }

  /**
   * Get current playback position
   */
  getCurrentTime(): number {
    const player = this.getCurrentPlayer();
    return player?.getCurrentTime() ?? 0;
  }

  /**
   * Get track duration
   */
  getDuration(): number {
    const player = this.getCurrentPlayer();
    return player?.getDuration() ?? 0;
  }

  /**
   * Get current player state
   */
  getState(): PlayerState {
    return this.state;
  }

  /**
   * Get current player mode
   */
  getMode(): PlayerMode {
    return this.currentMode;
  }

  /**
   * Get audio element (for volume control, etc.)
   */
  getAudioElement(): HTMLAudioElement | null {
    const player = this.getCurrentPlayer();
    return player?.getAudioElement() ?? null;
  }

  /**
   * Set volume (0-1)
   */
  setVolume(volume: number): void {
    const audio = this.getAudioElement();
    if (audio) audio.volume = Math.max(0, Math.min(1, volume));
  }

  /**
   * Event subscription
   */
  on(event: PlayerEvent, callback: EventCallback): () => void {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, new Set());
    }
    this.eventListeners.get(event)!.add(callback);

    // Return unsubscribe function
    return () => {
      this.eventListeners.get(event)?.delete(callback);
    };
  }

  /**
   * Emit event
   */
  private emit(event: PlayerEvent, data?: any): void {
    this.eventListeners.get(event)?.forEach(callback => callback(data));
  }

  /**
   * Update state and emit event
   */
  private setState(state: PlayerState): void {
    if (this.state === state) return;

    const oldState = this.state;
    this.state = state;
    this.emit('statechange', { oldState, newState: state });
  }

  /**
   * Get current active player
   */
  private getCurrentPlayer(): MSEPlayerInternal | HTML5AudioPlayerInternal | null {
    return this.currentMode === 'mse' ? this.msePlayer : this.html5Player;
  }

  /**
   * Clean up resources
   */
  cleanup(): void {
    this.debug('Cleaning up UnifiedPlayerManager');

    if (this.msePlayer) {
      this.msePlayer.cleanup();
      this.msePlayer = null;
    }

    if (this.html5Player) {
      this.html5Player.cleanup();
      this.html5Player = null;
    }

    this.eventListeners.clear();
    this.setState('idle');
    this.currentTrackId = null;
  }
}

export default UnifiedPlayerManager;
