/**
 * WorkletOutput - the AudioWorklet half of BufferScheduler.
 *
 * Split out of BufferScheduler.ts (#5840). Owns the AudioWorkletNode, its
 * message port, the feed interval, and the lookahead accounting (#5657): the
 * worklet queue is unbounded and sits out of sight of the PCMStreamBuffer, so
 * the feeder tracks what it has sent against the played count the worklet
 * reports back, and tops the queue up to a fixed lookahead instead of pushing
 * faster than real time. The ScriptProcessorNode fallback stays in
 * BufferScheduler.
 *
 * @copyright (C) 2024 Auralis Team
 * @license AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
 */

import type { BufferHealth } from './bufferHealth';
import type PCMStreamBuffer from './PCMStreamBuffer';
import { PLAYBACK_ENGINE_CONFIG } from './audioConstants';

export interface WorkletOutputCallbacks {
  /** Worklet reports an absolute samples-played count. */
  onSamplesPlayedSet: (count: number) => void;
  onUnderrun: () => void;
}

export class WorkletOutput {
  private node: AudioWorkletNode | null = null;
  private feedInterval: ReturnType<typeof setInterval> | null = null;
  private framesSent: number = 0;
  private framesPlayed: number = 0;

  constructor(
    private audioContext: AudioContext,
    private buffer: PCMStreamBuffer,
    private gainNode: GainNode,
    private health: BufferHealth,
    private callbacks: WorkletOutputCallbacks
  ) {}

  /** Whether a worklet node currently exists (running or held by pause()). */
  get isActive(): boolean {
    return this.node !== null;
  }

  /**
   * Frames queued inside the worklet but not yet played (an upper bound: the
   * played count arrives about every 0.37 s, so this never under-reports).
   */
  private getLookaheadFrames(): number {
    return Math.max(0, this.framesSent - this.framesPlayed);
  }

  /**
   * Load AudioWorklet module (one-time initialization)
   * @returns true if AudioWorklet is available and module loaded
   */
  async init(): Promise<boolean> {
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
   * Create AudioWorkletNode for off-main-thread audio processing (#2347).
   * Returns false on failure so the caller can fall back to a
   * ScriptProcessorNode.
   */
  create(): boolean {
    if (this.node) {
      // Idempotent, and also the way out of a soft pause: a worklet held by
      // pause() is still alive, so "create" has to mean "make it play".
      this.node.port.postMessage({ command: 'resume' });
      this.startFeeding();
      return true;
    }

    try {
      const channels = this.buffer.getMetadata().channels || 2;
      this.node = new AudioWorkletNode(
        this.audioContext,
        'auralis-playback-processor',
        { outputChannelCount: [channels] }
      );

      // Tell the worklet how many channels to deinterleave (#2842)
      this.node.port.postMessage({ command: 'setChannels', channels });

      // A fresh worklet starts with an empty queue and a played count of 0.
      this.framesSent = 0;
      this.framesPlayed = 0;

      this.node.port.onmessage = (event: MessageEvent) => {
        const { data } = event;
        if (data.type === 'underrun') {
          this.health.countUnderrun();
          this.callbacks.onUnderrun();
          this.health.setStalled(true);
        } else if (data.type === 'samplesPlayed') {
          this.framesPlayed = data.count;
          this.callbacks.onSamplesPlayedSet(data.count);
          // The worklet reports progress only while it is writing audio, so
          // this is the recovery signal for a hard underrun.
          if (!this.health.isPaused) this.health.setStalled(false);
        }
      };

      this.node.connect(this.gainNode);
      this.startFeeding();

      console.log('[BufferScheduler] AudioWorkletNode created (off-main-thread processing)');
      return true;
    } catch (error) {
      console.error('[BufferScheduler] Failed to create AudioWorkletNode, falling back:', error);
      return false;
    }
  }

  /** Stop feeding and tear the node down, discarding its queue. */
  disconnect(): void {
    this.stopFeeding();
    if (this.node) {
      this.node.port.postMessage({ command: 'clear' });
      this.node.disconnect();
      this.node = null;
    }
  }

  /** Hold output without losing audio: keep the queue and the played count. */
  pause(): void {
    if (!this.node) return;
    this.stopFeeding();
    this.node.port.postMessage({ command: 'pause' });
  }

  /** Counterpart of pause(): continue from exactly where output was held. */
  resume(): void {
    if (!this.node) return;
    this.node.port.postMessage({ command: 'resume' });
    this.startFeeding();
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
      if (!this.node) return;

      const { sampleRate: rate, channels: ch } = this.buffer.getMetadata();
      const sampleRate = rate || 44100;
      const bufferChannels = ch || 2;
      const lookaheadFrames = this.getLookaheadFrames();
      const ringFrames = this.buffer.getAvailableSamples() / bufferChannels;
      // Everything not yet played: still in the ring plus already in the worklet.
      const bufferedSeconds = (ringFrames + lookaheadFrames) / sampleRate;

      // The worklet reports a stall itself once its queue runs dry, so a
      // low-water pause here must not flag one while it is still playing.
      if (!this.health.check(bufferedSeconds, 'feed', false)) return;

      const targetFrames = Math.round(PLAYBACK_ENGINE_CONFIG.workletLookaheadSeconds * sampleRate);
      const creditFrames = Math.min(
        targetFrames - lookaheadFrames,
        PLAYBACK_ENGINE_CONFIG.maxFeedFramesPerTick
      );
      if (creditFrames <= 0) return;

      const samples = this.buffer.read(creditFrames * bufferChannels);
      if (samples.length > 0) {
        const frames = samples.length / bufferChannels;
        // Transfer the ArrayBuffer instead of letting structured-clone copy
        // it (#5665). `samples` is a fresh array from read() and dead after
        // this line — the transfer detaches it, so the length is read first.
        this.node.port.postMessage({ samples }, [samples.buffer]);
        this.framesSent += frames;
      }
    }, PLAYBACK_ENGINE_CONFIG.feedIntervalMs);
  }

  /** Stop feeding samples to AudioWorklet */
  private stopFeeding(): void {
    if (this.feedInterval) {
      clearInterval(this.feedInterval);
      this.feedInterval = null;
    }
  }
}

export default WorkletOutput;
