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
 * @license GPLv3, see LICENSE for more details
 */

import PCMStreamBuffer from './PCMStreamBuffer';
import { PLAYBACK_ENGINE_CONFIG } from './audioConstants';
import { BufferScheduler } from './BufferScheduler';
import { PlaybackPositionTracker, type PlaybackState } from './PlaybackPositionTracker';

export type { PlaybackState } from './PlaybackPositionTracker';

/**
 * Create or get a shared AnalyserNode for visualization
 * Stores in global for useAudioVisualization hook to access
 */
function createGlobalAnalyser(audioContext: AudioContext): AnalyserNode {
  const existing = window.__auralisAnalyser;
  // Reuse only when the cached node belongs to the same, non-closed context.
  // When usePlayEnhanced replaces an AudioContext (e.g. sample-rate change), the
  // stale analyser belongs to the closed old context; connecting a gainNode from
  // the new context to it throws DOMException: InvalidStateError (fixes #2488).
  if (existing && existing.context === audioContext && audioContext.state !== 'closed') {
    return existing;
  }

  const analyser = audioContext.createAnalyser();
  analyser.fftSize = PLAYBACK_ENGINE_CONFIG.fftSize;
  analyser.smoothingTimeConstant = PLAYBACK_ENGINE_CONFIG.smoothingTimeConstant;
  window.__auralisAnalyser = analyser;

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
  private bufferScheduler: BufferScheduler;
  private positionTracker: PlaybackPositionTracker;
  private volume: number = 1.0;

  // Callbacks
  private onBufferUnderrun: () => void = () => {};

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
    });

    console.log('[AudioPlaybackEngine] Audio chain connected with visualization analyser');
  }

  /**
   * Expose the engine-level minimum buffer threshold so callers can align their
   * own pre-checks with the gate enforced inside startPlayback() (#2478).
   */
  getMinBufferSamples(): number {
    return this.bufferScheduler.getMinBufferSamples();
  }

  /**
   * Start playback from buffer
   * Requires sufficient samples in buffer (minBufferSamples)
   * Note: This is now async to properly handle AudioContext resume
   */
  async startPlayback(): Promise<void> {
    if (this.positionTracker.isPlaying()) {
      return; // Already playing
    }

    const availableSamples = this.buffer.getAvailableSamples();
    const minBufferSamples = this.bufferScheduler.getMinBufferSamples();
    if (availableSamples < minBufferSamples) {
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
        } catch (err) {
          console.error('[AudioPlaybackEngine] Failed to resume AudioContext:', err);
          this.positionTracker.setState('error');
          return; // Can't continue without AudioContext
        }
      }

      // Try AudioWorklet (off-main-thread), fall back to ScriptProcessorNode
      await this.bufferScheduler.ensureReady();
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

    // Disconnect processor (worklet or script)
    this.bufferScheduler.disconnectProcessor();

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

    // Resume from paused time
    this.bufferScheduler.createProcessor();
    this.positionTracker.setState('playing');
    console.log('[AudioPlaybackEngine] Playback resumed from', this.getCurrentPlaybackTime().toFixed(2), 's');
  }

  /**
   * Stop playback completely
   */
  stopPlayback(): void {
    this.bufferScheduler.disconnectProcessor();

    this.positionTracker.reset();
    this.bufferScheduler.resetUnderrunCount();
    this.bufferScheduler.resetBufferHealth();

    this.positionTracker.setState('stopped');
    console.log('[AudioPlaybackEngine] Playback stopped');
  }

  /**
   * Fully tear down this engine's Web Audio graph.
   *
   * disconnectProcessor()/stopPlayback() only tear down the worklet/script
   * nodes; the gainNode is wired permanently in the constructor
   * (gainNode → analyser → destination) and is never otherwise disconnected.
   * In enhanced mode the AudioContext stays open across track switches
   * (closeContextOnCleanup: false), so without this each new engine strands the
   * previous engine's gainNode — connected to the analyser for the life of the
   * context (#4445). Idempotent; safe to call after the context has closed.
   */
  dispose(): void {
    this.bufferScheduler.disconnectProcessor();
    try {
      this.gainNode.disconnect();
    } catch {
      // Node already disconnected or its context is closed — nothing to free.
    }
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
    this.positionTracker.setSeekOffset(offsetSeconds);
  }

  /**
   * Get current playback time in seconds
   */
  getCurrentPlaybackTime(): number {
    return this.positionTracker.getCurrentPlaybackTime(this.buffer.getMetadata().sampleRate);
  }

  /**
   * Get playback statistics
   */
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
   * Check current state
   */
  isPlaying(): boolean {
    return this.positionTracker.isPlaying();
  }
}

export default AudioPlaybackEngine;
