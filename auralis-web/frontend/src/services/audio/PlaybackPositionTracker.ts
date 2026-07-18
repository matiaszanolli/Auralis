/**
 * PlaybackPositionTracker - playback state and position/timing tracking
 *
 * Split out of AudioPlaybackEngine.ts (#4301) — owns the playback state
 * machine (idle/playing/paused/stopped/error), sample-based position
 * tracking, seek offset, and paused-time bookkeeping. Knows nothing about
 * Web Audio nodes or buffer feeding.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

export type PlaybackState = 'idle' | 'playing' | 'paused' | 'stopped' | 'error';

export class PlaybackPositionTracker {
  private state: PlaybackState = 'idle';
  private samplesPlayed: number = 0;
  private pausedTime: number = 0;
  // Seek offset: when streaming resumes from a non-zero position the time
  // display must start from that position rather than 0:00 (fixes #2259).
  private seekOffsetSeconds: number = 0;

  private onStateChange: (state: PlaybackState) => void = () => {};

  getState(): PlaybackState {
    return this.state;
  }

  isPlaying(): boolean {
    return this.state === 'playing';
  }

  setState(newState: PlaybackState): void {
    if (this.state !== newState) {
      this.state = newState;
      this.onStateChange(newState);
    }
  }

  onStateChanged(callback: (state: PlaybackState) => void): () => void {
    this.onStateChange = callback;
    return () => {
      this.onStateChange = () => {};
    };
  }

  setSamplesPlayed(count: number): void {
    this.samplesPlayed = count;
  }

  addSamplesPlayed(delta: number): void {
    this.samplesPlayed += delta;
  }

  getSamplesPlayed(): number {
    return this.samplesPlayed;
  }

  setPausedTime(time: number): void {
    this.pausedTime = time;
  }

  setSeekOffset(offsetSeconds: number): void {
    this.seekOffsetSeconds = Math.max(0, offsetSeconds);
  }

  /**
   * Reset all position bookkeeping (used by stopPlayback).
   */
  reset(): void {
    this.pausedTime = 0;
    this.samplesPlayed = 0;
    this.seekOffsetSeconds = 0;
  }

  /**
   * Get current playback time in seconds, given the stream's sample rate.
   */
  getCurrentPlaybackTime(sampleRate: number): number {
    if (this.state === 'idle' || this.state === 'stopped') {
      return 0;
    }

    if (this.state === 'paused') {
      return this.pausedTime;
    }

    // Playing: calculate from samples played, offset by seek position
    return this.seekOffsetSeconds + this.samplesPlayed / sampleRate;
  }
}

export default PlaybackPositionTracker;
