/**
 * BufferScheduler - Web Audio node scheduling and buffer feeding
 *
 * Split out of AudioPlaybackEngine.ts (#4301) — owns the AudioWorklet
 * (off-main-thread) / ScriptProcessorNode fallback, pulls PCM samples from
 * a PCMStreamBuffer, and manages buffer-health water marks. Reports sample
 * progress and underruns to its caller via callbacks; knows nothing about
 * playback state or position formatting.
 *
 * The AudioWorklet path lives in WorkletOutput.ts and the water-mark
 * hysteresis in bufferHealth.ts (#5840); this class keeps the public surface,
 * the ScriptProcessorNode fallback, and the choice between the two.
 *
 * @copyright (C) 2024 Auralis Team
 * @license AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
 */

import PCMStreamBuffer from './PCMStreamBuffer';
import { DEFAULT_STREAM_SAMPLE_RATE, PLAYBACK_ENGINE_CONFIG } from './audioConstants';
import { BufferHealth } from './bufferHealth';
import { deinterleaveToOutput } from './deinterleaveToOutput';
import { WorkletOutput } from './WorkletOutput';

export interface BufferSchedulerCallbacks {
  /** Worklet reports an absolute samples-played count. */
  onSamplesPlayedSet: (count: number) => void;
  /** Script processor fallback reports an incremental samples-played delta. */
  onSamplesPlayedIncrement: (delta: number) => void;
  onUnderrun: () => void;
  /** Output went silent for lack of audio (`true`) or recovered (`false`) —
   *  low-water pauses and hard underruns alike, transitions only (#5461). */
  onStallChange?: (stalled: boolean) => void;
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
  private workletReady: boolean = false;
  private worklet: WorkletOutput;
  private health: BufferHealth;

  // Configuration (centralised in audioConstants.ts — #4031)
  private bufferSize: number = PLAYBACK_ENGINE_CONFIG.bufferSize; // samples per process callback
  // #6232: derived per query from the stream's own metadata — see
  // getMinBufferSamples().
  private get minBufferSamples(): number {
    const meta = this.buffer.getMetadata();
    const rate = meta.sampleRate || DEFAULT_STREAM_SAMPLE_RATE;
    const channels = meta.channels || 2;
    return Math.ceil(PLAYBACK_ENGINE_CONFIG.minBufferSeconds * rate * channels);
  }

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
    this.health = new BufferHealth((stalled) => this.callbacks.onStallChange?.(stalled));
    this.worklet = new WorkletOutput(audioContext, buffer, gainNode, this.health, {
      onSamplesPlayedSet: (count) => this.callbacks.onSamplesPlayedSet(count),
      onUnderrun: () => this.callbacks.onUnderrun(),
    });
  }

  /**
   * Expose the minimum buffer threshold so callers can align their own
   * pre-checks with the gate enforced inside AudioPlaybackEngine.startPlayback() (#2478).
   */
  getMinBufferSamples(): number {
    return this.minBufferSamples;
  }

  getUnderrunCount(): number {
    return this.health.getUnderrunCount();
  }

  resetUnderrunCount(): void {
    this.health.resetUnderrunCount();
  }

  /**
   * The stream has delivered its last chunk. Play out whatever is buffered
   * instead of waiting for a refill to the high-water mark that cannot come —
   * otherwise the final seconds sit unplayed in the ring and the track never
   * reaches its end.
   */
  markStreamEnded(): void {
    this.health.markStreamEnded();
  }

  hasStreamEnded(): boolean {
    return this.health.hasStreamEnded();
  }

  /** Forget a previous stream's end (stop / seek restart the same engine). */
  resetStreamEnded(): void {
    this.health.resetStreamEnded();
  }

  resetBufferHealth(): void {
    this.health.reset();
  }

  /**
   * Load the AudioWorklet module if not already ready (one-time
   * initialization per instance, retried on prior failure). Call before
   * createProcessor().
   */
  async ensureReady(): Promise<void> {
    if (!this.workletReady) {
      this.workletReady = await this.worklet.init();
    }
  }

  /**
   * Create the appropriate processor (AudioWorklet or ScriptProcessorNode)
   */
  createProcessor(): void {
    if (this.workletReady) {
      // Falls back to a ScriptProcessorNode when the worklet node can't be built.
      if (!this.worklet.create()) {
        this.workletReady = false;
        this.createScriptProcessor();
      }
    } else {
      this.createScriptProcessor();
    }
  }

  /**
   * Disconnect active processor (worklet or script) and stop feeding
   */
  disconnectProcessor(): void {
    this.worklet.disconnect();
    if (this.scriptNode) {
      this.scriptNode.disconnect();
      this.scriptNode = null;
    }
  }

  /**
   * Hold output without losing audio, for pause.
   *
   * The worklet keeps its queue and played count while paused; tearing it down
   * (disconnectProcessor) discarded that lookahead after the ring had already
   * advanced past it, so resume skipped it, and the replacement worklet restarted
   * its played count at 0 so the reported position jumped back (#5657). The
   * ScriptProcessorNode fallback pulls on demand — nothing is queued in it — so
   * it can simply be disconnected.
   */
  pauseOutput(): void {
    if (this.worklet.isActive) {
      this.worklet.pause();
    } else {
      this.disconnectProcessor();
    }
  }

  /** Counterpart of pauseOutput(): continue from exactly where output was held. */
  resumeOutput(): void {
    if (this.worklet.isActive) {
      this.worklet.resume();
    } else {
      this.createProcessor();
    }
  }

  /**
   * Create ScriptProcessorNode for sample pulling (legacy fallback)
   * Used when AudioWorklet is not available.
   *
   * #4623 — DELIBERATELY KEPT, do not re-report as dead deprecated API.
   * ScriptProcessorNode was deprecated in 2014 and Electron's Chromium always
   * provides AudioWorklet, so the *capability* check at `initWorklet()` can
   * never fail here. The branch is still reachable for two reasons that have
   * nothing to do with browser support:
   *
   *   1. `audioWorklet.addModule('/audio-worklet-processor.js')` fetches a
   *      static asset. In a packaged build a bad base path or a missing file
   *      makes that reject — a deployment failure, not a capability one.
   *   2. `new AudioWorkletNode(...)` throws if the processor name was never
   *      registered (e.g. the module loaded but errored during evaluation).
   *
   * Both degrade audio to main-thread processing rather than failing loudly,
   * which is the correct trade against silence. Its tests
   * (`__tests__/BufferScheduler.test.ts`, `__tests__/AudioPlaybackEngine.test.ts`)
   * therefore cover a live path and must be kept.
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
    const sampleRate = this.buffer.getMetadata().sampleRate || DEFAULT_STREAM_SAMPLE_RATE;
    const samplesNeeded = framesNeeded * bufferChannels;

    // Check buffer health BEFORE reading
    const availableSamples = this.buffer.getAvailableSamples();
    const bufferedSeconds = availableSamples / (sampleRate * bufferChannels);

    if (!this.health.check(bufferedSeconds, 'playback')) {
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
      const underrunCount = this.health.countUnderrun();
      console.warn(
        `[BufferScheduler] Buffer underrun #${underrunCount}. ` +
        `Expected ${samplesNeeded} samples, got 0`
      );

      // Fill output with silence
      for (let ch = 0; ch < channelCount; ch++) {
        output.getChannelData(ch).fill(0);
      }

      // Notify of underrun
      this.callbacks.onUnderrun();
      this.health.setStalled(true);
      return;
    }

    this.health.setStalled(false);

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
