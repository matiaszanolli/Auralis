/**
 * AudioPlaybackEngine - Web Audio API playback scheduling
 *
 * Manages real-time playback of PCM samples from circular buffer via Web Audio API.
 * Features:
 * - Efficient sample pulling from PCMStreamBuffer
 * - ScriptProcessorNode + AudioWorklet fallback
 * - Volume and gain control
 * - Pause/resume functionality
 * - Buffer underrun detection
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import PCMStreamBuffer from './PCMStreamBuffer';

export type PlaybackState = 'idle' | 'playing' | 'paused' | 'stopped' | 'error';

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
  private state: PlaybackState = 'idle';
  private volume: number = 1.0;

  // Playback timing
  private audioContextStartTime: number = 0;
  private playbackStartTime: number = 0;
  private samplesPlayed: number = 0;
  private bufferUnderrunCount: number = 0;

  // Configuration
  private bufferSize: number = 4096; // samples per process callback
  private minBufferSamples: number = 48000; // ~1 second at 48kHz before starting playback
  private pausedTime: number = 0;

  // Buffer health thresholds (in seconds of audio)
  // When buffer drops below lowWaterMark, pause playback to let it recover
  // Resume playback when buffer rises above highWaterMark
  private lowWaterMarkSeconds: number = 3.0;  // Pause when < 3 seconds buffered
  private highWaterMarkSeconds: number = 5.0; // Resume when > 5 seconds buffered
  private isBufferPaused: boolean = false;    // Track if we paused due to low buffer

  // Callbacks
  private onStateChange: (state: PlaybackState) => void = () => {};
  private onBufferUnderrun: () => void = () => {};

  constructor(audioContext: AudioContext, buffer: PCMStreamBuffer) {
    this.audioContext = audioContext;
    this.buffer = buffer;

    // Create gain node
    this.gainNode = audioContext.createGain();
    this.gainNode.gain.value = this.volume;
    this.gainNode.connect(audioContext.destination);
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

      // Create ScriptProcessorNode for sample pulling
      this.createScriptProcessor();

      // Record timing
      this.audioContextStartTime = this.audioContext.currentTime;
      this.playbackStartTime = Date.now();
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

    // Disconnect script processor
    if (this.scriptNode) {
      this.scriptNode.disconnect();
      this.scriptNode = null;
    }

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
    this.playbackStartTime = Date.now() - (this.pausedTime * 1000);
    this.createScriptProcessor();
    this.setState('playing');
    console.log('[AudioPlaybackEngine] Playback resumed from', this.pausedTime.toFixed(2), 's');
  }

  /**
   * Stop playback completely
   */
  stopPlayback(): void {
    if (this.scriptNode) {
      this.scriptNode.disconnect();
      this.scriptNode = null;
    }

    this.pausedTime = 0;
    this.audioContextStartTime = 0;
    this.playbackStartTime = 0;
    this.samplesPlayed = 0;
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
   * Get current playback time in seconds
   */
  getCurrentPlaybackTime(): number {
    if (this.state === 'idle' || this.state === 'stopped') {
      return 0;
    }

    if (this.state === 'paused') {
      return this.pausedTime;
    }

    // Playing: calculate from samples played
    const sampleRate = this.buffer.getMetadata().sampleRate;
    return this.samplesPlayed / sampleRate;
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
   * Create ScriptProcessorNode for sample pulling
   * This is the audio callback that pulls samples from the buffer
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

      console.log('[AudioPlaybackEngine] ScriptProcessorNode created with buffer size:', this.bufferSize);
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
