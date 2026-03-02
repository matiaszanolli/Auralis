/**
 * AudioPlaybackEngine - Web Audio API playback scheduling
 *
 * Manages real-time playback of PCM samples from circular buffer via Web Audio API.
 * Features:
 * - Efficient sample pulling from PCMStreamBuffer
 * - AudioWorklet (off-main-thread) with ScriptProcessorNode fallback
 * - Volume and gain control
 * - Pause/resume functionality
 * - Buffer underrun detection
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import PCMStreamBuffer from './PCMStreamBuffer';

export type PlaybackState = 'idle' | 'playing' | 'paused' | 'stopped' | 'error';

/**
 * Create or get a shared AnalyserNode for visualization
 * Stores in global for useAudioVisualization hook to access
 */
function createGlobalAnalyser(audioContext: AudioContext): AnalyserNode {
  const existing = (window as any).__auralisAnalyser as AnalyserNode | undefined;
  // Reuse only when the cached node belongs to the same, non-closed context.
  // When usePlayEnhanced replaces an AudioContext (e.g. sample-rate change), the
  // stale analyser belongs to the closed old context; connecting a gainNode from
  // the new context to it throws DOMException: InvalidStateError (fixes #2488).
  if (existing && existing.context === audioContext && audioContext.state !== 'closed') {
    return existing;
  }

  const analyser = audioContext.createAnalyser();
  analyser.fftSize = 2048;
  analyser.smoothingTimeConstant = 0.8;
  (window as any).__auralisAnalyser = analyser;

  return analyser;
}

export interface PlaybackStats {
  isPlaying: boolean;
  currentTime: number;
  samplesPlayed: number;
  bufferUnderuns: number;
}

/**
 * AudioPlaybackEngine - Manages real-time playback of PCM samples
 */
export class AudioPlaybackEngine {
  private audioContext: AudioContext;
  private buffer: PCMStreamBuffer;
  private gainNode: GainNode;
  private scriptNode: ScriptProcessorNode | null = null;
  private workletNode: AudioWorkletNode | null = null;
  private feedInterval: ReturnType<typeof setInterval> | null = null;
  private workletReady: boolean = false;
  private state: PlaybackState = 'idle';
  private volume: number = 1.0;

  // Playback timing
  private samplesPlayed: number = 0;
  private bufferUnderrunCount: number = 0;
  // Seek offset: when streaming resumes from a non-zero position the time
  // display must start from that position rather than 0:00 (fixes #2259).
  private seekOffsetSeconds: number = 0;

  // Configuration
  private bufferSize: number = 4096; // samples per process callback
  private minBufferSamples: number = 240000; // ~5 seconds at 48kHz before starting playback (prevents immediate underrun)
  private pausedTime: number = 0;

  // Buffer health thresholds (in seconds of audio)
  // When buffer drops below lowWaterMark, pause playback to let it recover
  // Resume playback when buffer rises above highWaterMark
  // Note: Chunks are 15s long, delivered in ~9 frames. Water marks set to
  // accommodate chunk delivery latency and prevent underruns during streaming.
  private lowWaterMarkSeconds: number = 8.0;  // Pause when < 8 seconds buffered (prevents underrun during frame delivery)
  private highWaterMarkSeconds: number = 12.0; // Resume when > 12 seconds buffered (ensure smooth playback)
  private isBufferPaused: boolean = false;    // Track if we paused due to low buffer

  // Callbacks
  private onStateChange: (state: PlaybackState) => void = () => {};
  private onBufferUnderrun: () => void = () => {};

  constructor(audioContext: AudioContext, buffer: PCMStreamBuffer) {
    this.audioContext = audioContext;
    this.buffer = buffer;

    // Register AudioContext globally for visualization hook
    (window as any).__auralisAudioContext = audioContext;

    // Create gain node
    this.gainNode = audioContext.createGain();
    this.gainNode.gain.value = this.volume;

    // Connect through visualization analyser if available
    // Chain: gainNode → analyser → destination
    const analyser = createGlobalAnalyser(audioContext);
    this.gainNode.connect(analyser);
    analyser.connect(audioContext.destination);

    console.log('[AudioPlaybackEngine] Audio chain connected with visualization analyser');
  }

  /**
   * Expose the engine-level minimum buffer threshold so callers can align their
   * own pre-checks with the gate enforced inside startPlayback() (#2478).
   */
  getMinBufferSamples(): number {
    return this.minBufferSamples;
  }

  /**
   * Start playback from buffer
   * Requires sufficient samples in buffer (minBufferSamples)
   * Note: This is now async to properly handle AudioContext resume
   */
  async startPlayback(): Promise<void> {
    if (this.state === 'playing') {
      return; // Already playing
    }

    const availableSamples = this.buffer.getAvailableSamples();
    if (availableSamples < this.minBufferSamples) {
      console.warn(
        `[AudioPlaybackEngine] Insufficient buffer for playback. ` +
        `Available: ${availableSamples}, Required: ${this.minBufferSamples}`
      );
      this.setState('error');
      this.onBufferUnderrun();
      return;
    }

    try {
      // Ensure AudioContext is running (required on iOS/Safari after user interaction)
      if (this.audioContext.state === 'suspended') {
        console.log('[AudioPlaybackEngine] AudioContext suspended, resuming...');
        try {
          await this.audioContext.resume();
          console.log('[AudioPlaybackEngine] AudioContext resumed successfully');
        } catch (err) {
          console.error('[AudioPlaybackEngine] Failed to resume AudioContext:', err);
          this.setState('error');
          return; // Can't continue without AudioContext
        }
      }

      // Try AudioWorklet (off-main-thread), fall back to ScriptProcessorNode
      if (!this.workletReady) {
        this.workletReady = await this.initWorklet();
      }
      this.createProcessor();

      // Record timing
      this.samplesPlayed = 0;
      this.isBufferPaused = false; // Ensure clean buffer health state

      this.setState('playing');
      console.log('[AudioPlaybackEngine] Playback started');
    } catch (error) {
      console.error('[AudioPlaybackEngine] Failed to start playback:', error);
      this.setState('error');
    }
  }

  /**
   * Pause playback (can be resumed)
   */
  pausePlayback(): void {
    if (this.state !== 'playing') {
      return;
    }

    // Record pause time for resuming
    this.pausedTime = this.getCurrentPlaybackTime();

    // Disconnect processor (worklet or script)
    this.disconnectProcessor();

    this.setState('paused');
    console.log('[AudioPlaybackEngine] Playback paused at', this.pausedTime.toFixed(2), 's');
  }

  /**
   * Resume playback from pause
   */
  resumePlayback(): void {
    if (this.state !== 'paused') {
      return;
    }

    // Resume from paused time
    this.createProcessor();
    this.setState('playing');
    console.log('[AudioPlaybackEngine] Playback resumed from', this.pausedTime.toFixed(2), 's');
  }

  /**
   * Stop playback completely
   */
  stopPlayback(): void {
    this.disconnectProcessor();

    this.pausedTime = 0;
    this.samplesPlayed = 0;
    this.seekOffsetSeconds = 0;
    this.bufferUnderrunCount = 0;
    this.isBufferPaused = false; // Reset buffer health state

    this.setState('stopped');
    console.log('[AudioPlaybackEngine] Playback stopped');
  }

  /**
   * Set playback volume (0.0 - 1.0)
   */
  setVolume(volume: number): void {
    const clipped = Math.max(0, Math.min(1, volume));
    this.volume = clipped;
    this.gainNode.gain.value = clipped;
  }

  /**
   * Set a seek offset so the reported playback position starts from the seek
   * point rather than 0:00 (fixes #2259).  Call before startPlayback().
   */
  setSeekOffset(offsetSeconds: number): void {
    this.seekOffsetSeconds = Math.max(0, offsetSeconds);
  }

  /**
   * Get current playback time in seconds
   */
  getCurrentPlaybackTime(): number {
    if (this.state === 'idle' || this.state === 'stopped') {
      return 0;
    }

    if (this.state === 'paused') {
      return this.pausedTime;
    }

    // Playing: calculate from samples played, offset by seek position
    const sampleRate = this.buffer.getMetadata().sampleRate;
    return this.seekOffsetSeconds + this.samplesPlayed / sampleRate;
  }

  /**
   * Get playback statistics
   */
  getStats(): PlaybackStats {
    return {
      isPlaying: this.state === 'playing',
      currentTime: this.getCurrentPlaybackTime(),
      samplesPlayed: this.samplesPlayed,
      bufferUnderuns: this.bufferUnderrunCount
    };
  }

  /**
   * Register state change callback
   */
  onStateChanged(callback: (state: PlaybackState) => void): () => void {
    this.onStateChange = callback;
    // Return unsubscribe function
    return () => {
      this.onStateChange = () => {};
    };
  }

  /**
   * Register buffer underrun callback
   */
  onUnderrun(callback: () => void): () => void {
    this.onBufferUnderrun = callback;
    // Return unsubscribe function
    return () => {
      this.onBufferUnderrun = () => {};
    };
  }

  /**
   * Check current state
   */
  isPlaying(): boolean {
    return this.state === 'playing';
  }

  // ========================================================================
  // Private Methods
  // ========================================================================

  /**
   * Disconnect active processor (worklet or script) and stop feeding
   */
  private disconnectProcessor(): void {
    this.stopFeeding();
    if (this.workletNode) {
      this.workletNode.port.postMessage({ command: 'clear' });
      this.workletNode.disconnect();
      this.workletNode = null;
    }
    if (this.scriptNode) {
      this.scriptNode.disconnect();
      this.scriptNode = null;
    }
  }

  /**
   * Create the appropriate processor (AudioWorklet or ScriptProcessorNode)
   */
  private createProcessor(): void {
    if (this.workletReady) {
      this.createWorkletNode();
    } else {
      this.createScriptProcessor();
    }
  }

  /**
   * Load AudioWorklet module (one-time initialization)
   * @returns true if AudioWorklet is available and module loaded
   */
  private async initWorklet(): Promise<boolean> {
    try {
      if (!this.audioContext.audioWorklet) {
        return false;
      }
      await this.audioContext.audioWorklet.addModule('/audio-worklet-processor.js');
      console.log('[AudioPlaybackEngine] AudioWorklet module loaded successfully');
      return true;
    } catch (error) {
      console.warn('[AudioPlaybackEngine] AudioWorklet not available, using ScriptProcessorNode fallback:', error);
      return false;
    }
  }

  /**
   * Create AudioWorkletNode for off-main-thread audio processing (#2347)
   * Falls back to ScriptProcessorNode on failure.
   */
  private createWorkletNode(): void {
    if (this.workletNode) return;

    try {
      this.workletNode = new AudioWorkletNode(
        this.audioContext,
        'auralis-playback-processor',
        { outputChannelCount: [2] }
      );

      this.workletNode.port.onmessage = (event: MessageEvent) => {
        const { data } = event;
        if (data.type === 'underrun') {
          this.bufferUnderrunCount++;
          this.onBufferUnderrun();
        } else if (data.type === 'samplesPlayed') {
          this.samplesPlayed = data.count;
        }
      };

      this.workletNode.connect(this.gainNode);
      this.startFeeding();

      console.log('[AudioPlaybackEngine] AudioWorkletNode created (off-main-thread processing)');
    } catch (error) {
      console.error('[AudioPlaybackEngine] Failed to create AudioWorkletNode, falling back:', error);
      this.workletReady = false;
      this.createScriptProcessor();
    }
  }

  /**
   * Push samples from PCMStreamBuffer to AudioWorklet at regular intervals
   */
  private startFeeding(): void {
    if (this.feedInterval) return;

    const feedChunkSize = this.bufferSize * 2; // stereo interleaved

    this.feedInterval = setInterval(() => {
      if (!this.workletNode || this.state !== 'playing') return;

      const bufferChannels = this.buffer.getMetadata().channels || 2;
      const sampleRate = this.buffer.getMetadata().sampleRate || 44100;
      const available = this.buffer.getAvailableSamples();
      const bufferedSeconds = available / (sampleRate * bufferChannels);

      // Buffer health management (mirrors ScriptProcessorNode approach)
      if (!this.isBufferPaused && bufferedSeconds < this.lowWaterMarkSeconds) {
        this.isBufferPaused = true;
        console.warn(
          `[AudioPlaybackEngine] Buffer critically low (${bufferedSeconds.toFixed(1)}s). Pausing feed...`
        );
        return;
      }

      if (this.isBufferPaused) {
        if (bufferedSeconds >= this.highWaterMarkSeconds) {
          this.isBufferPaused = false;
          console.log(
            `[AudioPlaybackEngine] Buffer recovered (${bufferedSeconds.toFixed(1)}s). Resuming feed.`
          );
        } else {
          return;
        }
      }

      // Read and send samples to worklet
      const samples = this.buffer.read(feedChunkSize);
      if (samples.length > 0) {
        this.workletNode!.port.postMessage({ samples });
      }
    }, 50);
  }

  /**
   * Stop feeding samples to AudioWorklet
   */
  private stopFeeding(): void {
    if (this.feedInterval) {
      clearInterval(this.feedInterval);
      this.feedInterval = null;
    }
  }

  /**
   * Create ScriptProcessorNode for sample pulling (legacy fallback)
   * Used when AudioWorklet is not available.
   */
  private createScriptProcessor(): void {
    if (this.scriptNode) {
      return; // Already created
    }

    try {
      // Create script processor (4096 samples per callback is typical)
      this.scriptNode = this.audioContext.createScriptProcessor(this.bufferSize, 0, 2);

      // Audio processing callback - pulls samples from buffer
      this.scriptNode.onaudioprocess = (event: AudioProcessingEvent) => {
        this.handleAudioProcess(event);
      };

      // Connect to gain node
      this.scriptNode.connect(this.gainNode);

      console.log('[AudioPlaybackEngine] ScriptProcessorNode created (legacy fallback) with buffer size:', this.bufferSize);
    } catch (error) {
      console.error('[AudioPlaybackEngine] Failed to create ScriptProcessorNode:', error);
      this.setState('error');
    }
  }

  /**
   * Audio processing callback - called repeatedly by Web Audio API
   */
  private handleAudioProcess(event: AudioProcessingEvent): void {
    const output = event.outputBuffer;
    const channelCount = output.numberOfChannels;
    const framesNeeded = output.length; // Number of audio frames (samples per channel)

    // For stereo audio, we need framesNeeded * 2 interleaved samples
    // For mono, we need framesNeeded samples
    const bufferChannels = this.buffer.getMetadata().channels || 2;
    const sampleRate = this.buffer.getMetadata().sampleRate || 44100;
    const samplesNeeded = framesNeeded * bufferChannels;

    // Check buffer health BEFORE reading
    const availableSamples = this.buffer.getAvailableSamples();
    const bufferedSeconds = availableSamples / (sampleRate * bufferChannels);

    // Buffer health management: pause when critically low, resume when recovered
    if (!this.isBufferPaused && bufferedSeconds < this.lowWaterMarkSeconds) {
      // Buffer is getting critically low - stop reading to let it recover
      this.isBufferPaused = true;
      console.warn(
        `[AudioPlaybackEngine] Buffer critically low (${bufferedSeconds.toFixed(1)}s < ${this.lowWaterMarkSeconds}s). ` +
        `Pausing to let buffer recover...`
      );

      // Output silence while buffer recovers
      for (let ch = 0; ch < channelCount; ch++) {
        output.getChannelData(ch).fill(0);
      }
      return;
    }

    if (this.isBufferPaused) {
      // Check if buffer has recovered
      if (bufferedSeconds >= this.highWaterMarkSeconds) {
        this.isBufferPaused = false;
        console.log(
          `[AudioPlaybackEngine] Buffer recovered (${bufferedSeconds.toFixed(1)}s >= ${this.highWaterMarkSeconds}s). ` +
          `Resuming playback.`
        );
      } else {
        // Still recovering - output silence
        for (let ch = 0; ch < channelCount; ch++) {
          output.getChannelData(ch).fill(0);
        }
        return;
      }
    }

    // Read interleaved samples from buffer
    const samples = this.buffer.read(samplesNeeded);

    if (samples.length === 0) {
      // Buffer underrun - no samples available (shouldn't happen with health monitoring)
      this.bufferUnderrunCount++;
      console.warn(
        `[AudioPlaybackEngine] Buffer underrun #${this.bufferUnderrunCount}. ` +
        `Expected ${samplesNeeded} samples, got 0`
      );

      // Fill output with silence
      for (let ch = 0; ch < channelCount; ch++) {
        output.getChannelData(ch).fill(0);
      }

      // Notify of underrun
      this.onBufferUnderrun();
      return;
    }

    // If we got fewer samples than requested, we're running low
    if (samples.length < samplesNeeded) {
      console.warn(
        `[AudioPlaybackEngine] Low buffer. Expected ${samplesNeeded}, got ${samples.length} samples`
      );
    }

    // Copy samples to output channels
    if (bufferChannels === 1) {
      // Mono source - copy to all output channels
      const monoData = samples.subarray(0, framesNeeded);
      for (let ch = 0; ch < channelCount; ch++) {
        output.getChannelData(ch).set(monoData);
      }
    } else if (bufferChannels === 2) {
      // Stereo source - de-interleave samples
      const left = output.getChannelData(0);
      const right = output.getChannelData(1);
      const framesToProcess = Math.min(framesNeeded, Math.floor(samples.length / 2));

      for (let i = 0; i < framesToProcess; i++) {
        left[i] = samples[i * 2] || 0;
        right[i] = samples[i * 2 + 1] || 0;
      }

      // Fill remaining with silence if we didn't get enough samples
      for (let i = framesToProcess; i < framesNeeded; i++) {
        left[i] = 0;
        right[i] = 0;
      }
    } else {
      // Multichannel - distribute samples across channels
      for (let ch = 0; ch < channelCount; ch++) {
        const channelData = output.getChannelData(ch);
        for (let i = 0; i < framesNeeded; i++) {
          const sampleIndex = i * bufferChannels + ch;
          if (sampleIndex < samples.length) {
            channelData[i] = samples[sampleIndex];
          } else {
            channelData[i] = 0;
          }
        }
      }
    }

    // Update playback statistics (count frames, not interleaved samples)
    this.samplesPlayed += Math.floor(samples.length / bufferChannels);
  }

  /**
   * Update internal state and notify listeners
   */
  private setState(newState: PlaybackState): void {
    if (this.state !== newState) {
      this.state = newState;
      this.onStateChange(newState);
    }
  }
}

export default AudioPlaybackEngine;
