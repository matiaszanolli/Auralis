/**
 * BufferScheduler - Web Audio node scheduling and buffer feeding
 *
 * Split out of AudioPlaybackEngine.ts (#4301) — owns the AudioWorklet
 * (off-main-thread) / ScriptProcessorNode fallback, pulls PCM samples from
 * a PCMStreamBuffer, and manages buffer-health water marks. Reports sample
 * progress and underruns to its caller via callbacks; knows nothing about
 * playback state or position formatting.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import PCMStreamBuffer from './PCMStreamBuffer';
import { PLAYBACK_ENGINE_CONFIG } from './audioConstants';
import { deinterleaveToOutput } from './deinterleaveToOutput';

export interface BufferSchedulerCallbacks {
  /** Worklet reports an absolute samples-played count. */
  onSamplesPlayedSet: (count: number) => void;
  /** Script processor fallback reports an incremental samples-played delta. */
  onSamplesPlayedIncrement: (delta: number) => void;
  onUnderrun: () => void;
}

/**
 * Pulls PCM samples from a PCMStreamBuffer and feeds them to Web Audio via
 * an AudioWorkletNode (preferred) or ScriptProcessorNode (legacy fallback).
 */
export class BufferScheduler {
  private audioContext: AudioContext;
  private buffer: PCMStreamBuffer;
  private gainNode: GainNode;
  private callbacks: BufferSchedulerCallbacks;

  private scriptNode: ScriptProcessorNode | null = null;
  private workletNode: AudioWorkletNode | null = null;
  private feedInterval: ReturnType<typeof setInterval> | null = null;
  private workletReady: boolean = false;

  private bufferUnderrunCount: number = 0;
  private isBufferPaused: boolean = false; // Track if we paused due to low buffer

  // Configuration (centralised in audioConstants.ts — #4031)
  private bufferSize: number = PLAYBACK_ENGINE_CONFIG.bufferSize; // samples per process callback
  private minBufferSamples: number = PLAYBACK_ENGINE_CONFIG.minBufferSamples; // ~1s at 48kHz stereo — start playback quickly; water marks handle recovery

  // Buffer health thresholds (in seconds of audio). Water marks stay below the
  // backend chunk interval (CHUNK_INTERVAL = 10 s) so a single late chunk does
  // not trigger an avoidable pause. See audioConstants.ts.
  private lowWaterMarkSeconds: number = PLAYBACK_ENGINE_CONFIG.lowWaterMarkSeconds;  // Pause when < 5 seconds buffered
  private highWaterMarkSeconds: number = PLAYBACK_ENGINE_CONFIG.highWaterMarkSeconds; // Resume when > 8 seconds buffered

  constructor(
    audioContext: AudioContext,
    buffer: PCMStreamBuffer,
    gainNode: GainNode,
    callbacks: BufferSchedulerCallbacks
  ) {
    this.audioContext = audioContext;
    this.buffer = buffer;
    this.gainNode = gainNode;
    this.callbacks = callbacks;
  }

  /**
   * Expose the minimum buffer threshold so callers can align their own
   * pre-checks with the gate enforced inside AudioPlaybackEngine.startPlayback() (#2478).
   */
  getMinBufferSamples(): number {
    return this.minBufferSamples;
  }

  getUnderrunCount(): number {
    return this.bufferUnderrunCount;
  }

  resetUnderrunCount(): void {
    this.bufferUnderrunCount = 0;
  }

  resetBufferHealth(): void {
    this.isBufferPaused = false;
  }

  /**
   * Load the AudioWorklet module if not already ready (one-time
   * initialization per instance, retried on prior failure). Call before
   * createProcessor().
   */
  async ensureReady(): Promise<void> {
    if (!this.workletReady) {
      this.workletReady = await this.initWorklet();
    }
  }

  /**
   * Create the appropriate processor (AudioWorklet or ScriptProcessorNode)
   */
  createProcessor(): void {
    if (this.workletReady) {
      this.createWorkletNode();
    } else {
      this.createScriptProcessor();
    }
  }

  /**
   * Disconnect active processor (worklet or script) and stop feeding
   */
  disconnectProcessor(): void {
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
   * Load AudioWorklet module (one-time initialization)
   * @returns true if AudioWorklet is available and module loaded
   */
  private async initWorklet(): Promise<boolean> {
    try {
      if (!this.audioContext.audioWorklet) {
        return false;
      }
      await this.audioContext.audioWorklet.addModule('/audio-worklet-processor.js');
      console.log('[BufferScheduler] AudioWorklet module loaded successfully');
      return true;
    } catch (error) {
      console.warn('[BufferScheduler] AudioWorklet not available, using ScriptProcessorNode fallback:', error);
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
      const channels = this.buffer.getMetadata().channels || 2;
      this.workletNode = new AudioWorkletNode(
        this.audioContext,
        'auralis-playback-processor',
        { outputChannelCount: [channels] }
      );

      // Tell the worklet how many channels to deinterleave (#2842)
      this.workletNode.port.postMessage({ command: 'setChannels', channels });

      this.workletNode.port.onmessage = (event: MessageEvent) => {
        const { data } = event;
        if (data.type === 'underrun') {
          this.bufferUnderrunCount++;
          this.callbacks.onUnderrun();
        } else if (data.type === 'samplesPlayed') {
          this.callbacks.onSamplesPlayedSet(data.count);
        }
      };

      this.workletNode.connect(this.gainNode);
      this.startFeeding();

      console.log('[BufferScheduler] AudioWorkletNode created (off-main-thread processing)');
    } catch (error) {
      console.error('[BufferScheduler] Failed to create AudioWorkletNode, falling back:', error);
      this.workletReady = false;
      this.createScriptProcessor();
    }
  }

  /**
   * Push samples from PCMStreamBuffer to AudioWorklet at regular intervals
   */
  private startFeeding(): void {
    if (this.feedInterval) return;

    const channels = this.buffer.getMetadata().channels || 2;
    const feedChunkSize = this.bufferSize * channels; // interleaved samples per feed

    this.feedInterval = setInterval(() => {
      if (!this.workletNode) return;

      const bufferChannels = this.buffer.getMetadata().channels || 2;
      const sampleRate = this.buffer.getMetadata().sampleRate || 44100;
      const available = this.buffer.getAvailableSamples();
      const bufferedSeconds = available / (sampleRate * bufferChannels);

      if (!this.checkBufferHealth(bufferedSeconds, 'feed')) return;

      // Read and send samples to worklet
      const samples = this.buffer.read(feedChunkSize);
      if (samples.length > 0) {
        this.workletNode!.port.postMessage({ samples });
      }
    }, PLAYBACK_ENGINE_CONFIG.feedIntervalMs);
  }

  /**
   * Update buffer-health pause state given currently buffered seconds, and
   * return whether the caller should proceed to read/feed samples. Shared
   * by both the worklet feed loop and the ScriptProcessorNode callback so
   * the low/high water-mark hysteresis lives in exactly one place.
   */
  private checkBufferHealth(bufferedSeconds: number, context: 'feed' | 'playback'): boolean {
    if (!this.isBufferPaused && bufferedSeconds < this.lowWaterMarkSeconds) {
      this.isBufferPaused = true;
      console.warn(
        `[BufferScheduler] Buffer critically low (${bufferedSeconds.toFixed(1)}s < ${this.lowWaterMarkSeconds}s). ` +
        `Pausing ${context}...`
      );
      return false;
    }

    if (this.isBufferPaused) {
      if (bufferedSeconds >= this.highWaterMarkSeconds) {
        this.isBufferPaused = false;
        console.log(
          `[BufferScheduler] Buffer recovered (${bufferedSeconds.toFixed(1)}s >= ${this.highWaterMarkSeconds}s). ` +
          `Resuming ${context}.`
        );
      } else {
        return false;
      }
    }

    return true;
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
      const channels = this.buffer.getMetadata().channels || 2;
      this.scriptNode = this.audioContext.createScriptProcessor(this.bufferSize, 0, channels);

      // Audio processing callback - pulls samples from buffer
      this.scriptNode.onaudioprocess = (event: AudioProcessingEvent) => {
        this.handleAudioProcess(event);
      };

      // Connect to gain node
      this.scriptNode.connect(this.gainNode);

      console.log('[BufferScheduler] ScriptProcessorNode created (legacy fallback) with buffer size:', this.bufferSize);
    } catch (error) {
      // Swallowed intentionally to match pre-split AudioPlaybackEngine
      // behavior: startPlayback()'s subsequent setState('playing') call
      // always runs regardless of processor-creation failure here.
      console.error('[BufferScheduler] Failed to create ScriptProcessorNode:', error);
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

    if (!this.checkBufferHealth(bufferedSeconds, 'playback')) {
      // Paused or still recovering - output silence
      for (let ch = 0; ch < channelCount; ch++) {
        output.getChannelData(ch).fill(0);
      }
      return;
    }

    // Read interleaved samples from buffer
    const samples = this.buffer.read(samplesNeeded);

    if (samples.length === 0) {
      // Buffer underrun - no samples available (shouldn't happen with health monitoring)
      this.bufferUnderrunCount++;
      console.warn(
        `[BufferScheduler] Buffer underrun #${this.bufferUnderrunCount}. ` +
        `Expected ${samplesNeeded} samples, got 0`
      );

      // Fill output with silence
      for (let ch = 0; ch < channelCount; ch++) {
        output.getChannelData(ch).fill(0);
      }

      // Notify of underrun
      this.callbacks.onUnderrun();
      return;
    }

    // If we got fewer samples than requested, we're running low
    if (samples.length < samplesNeeded) {
      console.warn(
        `[BufferScheduler] Low buffer. Expected ${samplesNeeded}, got ${samples.length} samples`
      );
    }

    // Copy samples to output channels
    deinterleaveToOutput(output, samples, framesNeeded, bufferChannels);

    // Update playback statistics (count frames, not interleaved samples)
    this.callbacks.onSamplesPlayedIncrement(Math.floor(samples.length / bufferChannels));
  }
}

export default BufferScheduler;
