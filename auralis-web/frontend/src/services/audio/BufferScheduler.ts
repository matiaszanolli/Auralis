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
 * @license AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
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
  private workletNode: AudioWorkletNode | null = null;
  private feedInterval: ReturnType<typeof setInterval> | null = null;
  private workletReady: boolean = false;
  // Worklet lookahead accounting (#5657). The worklet queue is unbounded and sits
  // out of sight of the PCMStreamBuffer, so the feeder tracks what it has sent
  // against the played count the worklet reports back, and tops the queue up to
  // a fixed lookahead instead of pushing faster than real time.
  private workletFramesSent: number = 0;
  private workletFramesPlayed: number = 0;

  private bufferUnderrunCount: number = 0;
  private isBufferPaused: boolean = false; // Track if we paused due to low buffer
  // True once the backend has delivered everything it will (stream end). The
  // water marks then no longer apply: nothing more is coming to refill above
  // the low mark, so holding output would strand the tail of the track.
  private streamEnded: boolean = false;
  private stalled: boolean = false; // Last stall state reported via onStallChange

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

  /**
   * The stream has delivered its last chunk. Play out whatever is buffered
   * instead of waiting for a refill to the high-water mark that cannot come —
   * otherwise the final seconds sit unplayed in the ring and the track never
   * reaches its end.
   */
  markStreamEnded(): void {
    this.streamEnded = true;
    this.isBufferPaused = false;
  }

  /** Forget a previous stream's end (stop / seek restart the same engine). */
  resetStreamEnded(): void {
    this.streamEnded = false;
  }

  resetBufferHealth(): void {
    this.isBufferPaused = false;
    this.setStalled(false);
  }

  /** Report a stall transition. Low-water pauses and hard underruns share this
   *  one channel so the UI has a single signal to follow (#5461). */
  private setStalled(stalled: boolean): void {
    if (stalled === this.stalled) return;
    this.stalled = stalled;
    this.callbacks.onStallChange?.(stalled);
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
    if (this.workletNode) {
      this.stopFeeding();
      this.workletNode.port.postMessage({ command: 'pause' });
    } else {
      this.disconnectProcessor();
    }
  }

  /** Counterpart of pauseOutput(): continue from exactly where output was held. */
  resumeOutput(): void {
    if (this.workletNode) {
      this.workletNode.port.postMessage({ command: 'resume' });
      this.startFeeding();
    } else {
      this.createProcessor();
    }
  }

  /**
   * Frames queued inside the worklet but not yet played (an upper bound: the
   * played count arrives about every 0.37 s, so this never under-reports).
   */
  private getWorkletLookaheadFrames(): number {
    return Math.max(0, this.workletFramesSent - this.workletFramesPlayed);
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
    if (this.workletNode) {
      // Idempotent, and also the way out of a soft pause: a worklet held by
      // pauseOutput() is still alive, so "create" has to mean "make it play".
      this.workletNode.port.postMessage({ command: 'resume' });
      this.startFeeding();
      return;
    }

    try {
      const channels = this.buffer.getMetadata().channels || 2;
      this.workletNode = new AudioWorkletNode(
        this.audioContext,
        'auralis-playback-processor',
        { outputChannelCount: [channels] }
      );

      // Tell the worklet how many channels to deinterleave (#2842)
      this.workletNode.port.postMessage({ command: 'setChannels', channels });

      // A fresh worklet starts with an empty queue and a played count of 0.
      this.workletFramesSent = 0;
      this.workletFramesPlayed = 0;

      this.workletNode.port.onmessage = (event: MessageEvent) => {
        const { data } = event;
        if (data.type === 'underrun') {
          this.bufferUnderrunCount++;
          this.callbacks.onUnderrun();
          this.setStalled(true);
        } else if (data.type === 'samplesPlayed') {
          this.workletFramesPlayed = data.count;
          this.callbacks.onSamplesPlayedSet(data.count);
          // The worklet reports progress only while it is writing audio, so
          // this is the recovery signal for a hard underrun.
          if (!this.isBufferPaused) this.setStalled(false);
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
   * Push samples from PCMStreamBuffer to AudioWorklet at regular intervals.
   *
   * Each tick tops the worklet queue up to `workletLookaheadSeconds` (#5657).
   * It used to send 4096 frames every 50 ms regardless — about 1.7-1.86x real
   * time — into a queue with no bound, so the queue grew with track length and
   * the water marks (which only saw the ring) never reflected what was really
   * buffered.
   */
  private startFeeding(): void {
    if (this.feedInterval) return;

    this.feedInterval = setInterval(() => {
      if (!this.workletNode) return;

      const { sampleRate: rate, channels: ch } = this.buffer.getMetadata();
      const sampleRate = rate || 44100;
      const bufferChannels = ch || 2;
      const lookaheadFrames = this.getWorkletLookaheadFrames();
      const ringFrames = this.buffer.getAvailableSamples() / bufferChannels;
      // Everything not yet played: still in the ring plus already in the worklet.
      const bufferedSeconds = (ringFrames + lookaheadFrames) / sampleRate;

      // The worklet reports a stall itself once its queue runs dry, so a
      // low-water pause here must not flag one while it is still playing.
      if (!this.checkBufferHealth(bufferedSeconds, 'feed', false)) return;

      const targetFrames = Math.round(PLAYBACK_ENGINE_CONFIG.workletLookaheadSeconds * sampleRate);
      const creditFrames = Math.min(
        targetFrames - lookaheadFrames,
        PLAYBACK_ENGINE_CONFIG.maxFeedFramesPerTick
      );
      if (creditFrames <= 0) return;

      const samples = this.buffer.read(creditFrames * bufferChannels);
      if (samples.length > 0) {
        this.workletNode.port.postMessage({ samples });
        this.workletFramesSent += samples.length / bufferChannels;
      }
    }, PLAYBACK_ENGINE_CONFIG.feedIntervalMs);
  }

  /**
   * Update buffer-health pause state given currently buffered seconds, and
   * return whether the caller should proceed to read/feed samples. Shared
   * by both the worklet feed loop and the ScriptProcessorNode callback so
   * the low/high water-mark hysteresis lives in exactly one place.
   *
   * `reportStall` is false for the worklet feed loop: there a low-water pause
   * only stops feeding, audio already queued in the worklet keeps playing, and
   * the stall surfaces through the worklet's own underrun message.
   */
  private checkBufferHealth(
    bufferedSeconds: number,
    context: 'feed' | 'playback',
    reportStall: boolean = true
  ): boolean {
    if (this.streamEnded) return true;

    if (!this.isBufferPaused && bufferedSeconds < this.lowWaterMarkSeconds) {
      this.isBufferPaused = true;
      if (reportStall) this.setStalled(true);
      console.warn(
        `[BufferScheduler] Buffer critically low (${bufferedSeconds.toFixed(1)}s < ${this.lowWaterMarkSeconds}s). ` +
        `Pausing ${context}...`
      );
      return false;
    }

    if (this.isBufferPaused) {
      if (bufferedSeconds >= this.highWaterMarkSeconds) {
        this.isBufferPaused = false;
        this.setStalled(false);
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
      this.setStalled(true);
      return;
    }

    this.setStalled(false);

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
