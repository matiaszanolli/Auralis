/**
 * AudioPlaybackEngine - Web Audio API playback scheduling
 *
 * Manages real-time playback of PCM samples from circular buffer via Web Audio API.
 * Delegates to two focused collaborators (#4301):
 * - BufferScheduler: AudioWorklet/ScriptProcessorNode feeding and buffer health
 * - PlaybackPositionTracker: playback state machine and position/timing
 *
 * Features:
 * - Efficient sample pulling from PCMStreamBuffer
 * - AudioWorklet (off-main-thread) with ScriptProcessorNode fallback
 * - Volume and gain control
 * - Pause/resume functionality
 * - Buffer underrun detection
 *
 * @copyright (C) 2024 Auralis Team
 * @license AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
 */

import PCMStreamBuffer from './PCMStreamBuffer';
import { createGlobalAnalyser } from './globalAnalyser';
import { BufferScheduler } from './BufferScheduler';
import { PlaybackPositionTracker, type PlaybackState } from './PlaybackPositionTracker';

export type { PlaybackState } from './PlaybackPositionTracker';

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
  private bufferScheduler: BufferScheduler;
  private positionTracker: PlaybackPositionTracker;
  private volume: number = 1.0;
  // startPlayback() awaits a context resume and a worklet load; see startPlayback (#6043).
  private startAttempt = 0;
  private starting: Promise<void> | null = null;

  // Callbacks
  private onBufferUnderrun: () => void = () => {};
  private onStallChanged: (stalled: boolean) => void = () => {};

  constructor(audioContext: AudioContext, buffer: PCMStreamBuffer) {
    this.audioContext = audioContext;
    this.buffer = buffer;

    // Register AudioContext globally for visualization hook
    window.__auralisAudioContext = audioContext;

    // Create gain node
    this.gainNode = audioContext.createGain();
    this.gainNode.gain.value = this.volume;

    // Connect through visualization analyser if available
    // Chain: gainNode → analyser → destination
    const analyser = createGlobalAnalyser(audioContext);
    this.gainNode.connect(analyser);
    analyser.connect(audioContext.destination);

    this.positionTracker = new PlaybackPositionTracker();
    this.bufferScheduler = new BufferScheduler(audioContext, buffer, this.gainNode, {
      onSamplesPlayedSet: (count) => this.positionTracker.setSamplesPlayed(count),
      onSamplesPlayedIncrement: (delta) => this.positionTracker.addSamplesPlayed(delta),
      onUnderrun: () => this.onBufferUnderrun(),
      onStallChange: (stalled) => this.onStallChanged(stalled),
    });

    console.log('[AudioPlaybackEngine] Audio chain connected with visualization analyser');
  }

  /** The minimum-buffer gate startPlayback() enforces, so callers can pre-check it (#2478). */
  getMinBufferSamples(): number {
    return this.bufferScheduler.getMinBufferSamples();
  }

  /**
   * Start playback from buffer (needs minBufferSamples). Async: it awaits an AudioContext resume
   * and the worklet load. Chunks landing inside that window each ask to start, so they share one
   * attempt; a stop/dispose inside it cancels the attempt instead of being overtaken by it (#6043).
   */
  startPlayback(): Promise<void> {
    if (this.positionTracker.isPlaying()) return Promise.resolve();
    this.starting ??= this.start(this.startAttempt).finally(() => { this.starting = null; });
    return this.starting;
  }

  private async start(attempt: number): Promise<void> {
    const availableSamples = this.buffer.getAvailableSamples();
    const minBufferSamples = this.bufferScheduler.getMinBufferSamples();
    // A finished stream can never refill the buffer, so what it delivered is all there will be:
    // a seek into the last second or a sub-second track is shorter than the minimum (#5900).
    const streamIsComplete = this.bufferScheduler.hasStreamEnded() && availableSamples > 0;
    if (availableSamples < minBufferSamples && !streamIsComplete) {
      console.warn(
        `[AudioPlaybackEngine] Insufficient buffer for playback. ` +
        `Available: ${availableSamples}, Required: ${minBufferSamples}`
      );
      this.positionTracker.setState('error');
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
          if (attempt !== this.startAttempt) return;
        } catch (err) {
          console.error('[AudioPlaybackEngine] Failed to resume AudioContext:', err);
          this.positionTracker.setState('error');
          return; // Can't continue without AudioContext
        }
      }

      // Try AudioWorklet (off-main-thread), fall back to ScriptProcessorNode
      await this.bufferScheduler.ensureReady();
      if (attempt !== this.startAttempt) return; // stopped or disposed while the worklet loaded
      this.bufferScheduler.createProcessor();

      // Record timing
      this.positionTracker.setSamplesPlayed(0);
      this.bufferScheduler.resetBufferHealth(); // Ensure clean buffer health state

      this.positionTracker.setState('playing');
      console.log('[AudioPlaybackEngine] Playback started');
    } catch (error) {
      console.error('[AudioPlaybackEngine] Failed to start playback:', error);
      this.positionTracker.setState('error');
    }
  }

  /**
   * Pause playback (can be resumed)
   */
  pausePlayback(): void {
    if (!this.positionTracker.isPlaying()) {
      return;
    }

    // Record pause time for resuming
    this.positionTracker.setPausedTime(this.getCurrentPlaybackTime());

    // Hold output (worklet) or disconnect (script) without discarding audio (#5657)
    this.bufferScheduler.pauseOutput();

    this.positionTracker.setState('paused');
    console.log('[AudioPlaybackEngine] Playback paused at', this.getCurrentPlaybackTime().toFixed(2), 's');
  }

  /**
   * Resume playback from pause
   */
  resumePlayback(): void {
    if (this.positionTracker.getState() !== 'paused') {
      return;
    }

    // Resume from the held position
    this.bufferScheduler.resumeOutput();
    this.positionTracker.setState('playing');
    console.log('[AudioPlaybackEngine] Playback resumed from', this.getCurrentPlaybackTime().toFixed(2), 's');
  }

  /**
   * The stream has delivered its last chunk: play out the buffered tail rather
   * than holding it below the low-water mark.
   */
  markStreamEnded(): void {
    this.bufferScheduler.markStreamEnded();
  }

  /** True once the backend has delivered the stream's last chunk. */
  hasStreamEnded(): boolean {
    return this.bufferScheduler.hasStreamEnded();
  }

  /**
   * Clear the BufferHealth streamEnded latch (#5862). A previous stream's
   * terminal `audio_stream_end` latches it (disabling the 5s/8s low-water
   * hysteresis so the buffered tail can play out); an accepted NEW stream
   * must clear it or the rest of the track degrades to hard underruns. Only
   * stopPlayback used to, which re-issues and reconnects never call.
   */
  resetStreamEnded(): void {
    this.bufferScheduler.resetStreamEnded();
  }

  /** Stop playback completely */
  stopPlayback(): void {
    this.startAttempt += 1;
    this.bufferScheduler.disconnectProcessor();
    this.bufferScheduler.resetStreamEnded();

    this.positionTracker.reset();
    this.bufferScheduler.resetUnderrunCount();
    this.bufferScheduler.resetBufferHealth();

    this.positionTracker.setState('stopped');
    console.log('[AudioPlaybackEngine] Playback stopped');
  }

  /**
   * Fully tear down this engine's Web Audio graph. stopPlayback() only drops the worklet/script
   * nodes; the gainNode is wired permanently (gainNode → analyser → destination), and the context
   * stays open across track switches, so without this each engine strands its gainNode (#4445).
   * Idempotent; safe after the context has closed.
   */
  dispose(): void {
    this.startAttempt += 1;
    this.bufferScheduler.disconnectProcessor();
    try {
      this.gainNode.disconnect();
    } catch {
      // Node already disconnected or its context is closed — nothing to free.
    }
  }

  /** Set playback volume (0.0 - 1.0) */
  setVolume(volume: number): void {
    const clipped = Math.max(0, Math.min(1, volume));
    this.volume = clipped;
    this.gainNode.gain.value = clipped;
  }

  /** Report playback position from the seek point, not 0:00 (#2259). Call before startPlayback(). */
  setSeekOffset(offsetSeconds: number): void {
    this.positionTracker.setSeekOffset(offsetSeconds);
  }

  /** Get current playback time in seconds */
  getCurrentPlaybackTime(): number {
    return this.positionTracker.getCurrentPlaybackTime(this.buffer.getMetadata().sampleRate);
  }

  /** Get playback statistics */
  getStats(): PlaybackStats {
    return {
      isPlaying: this.positionTracker.isPlaying(),
      currentTime: this.getCurrentPlaybackTime(),
      samplesPlayed: this.positionTracker.getSamplesPlayed(),
      bufferUnderuns: this.bufferScheduler.getUnderrunCount()
    };
  }

  /**
   * Register state change callback
   */
  onStateChanged(callback: (state: PlaybackState) => void): () => void {
    return this.positionTracker.onStateChanged(callback);
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
   * Register a callback for local playback stalls (#5461): `true` when output
   * goes silent for lack of buffered audio (a low-water pause or a hard
   * underrun), `false` once audio flows again. Fires on transitions only.
   */
  onStallChange(callback: (stalled: boolean) => void): () => void {
    this.onStallChanged = callback;
    return () => {
      this.onStallChanged = () => {};
    };
  }

  /**
   * Check current state
   */
  isPlaying(): boolean {
    return this.positionTracker.isPlaying();
  }
}

export default AudioPlaybackEngine;
