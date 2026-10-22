/**
 * BufferHealth - low/high water-mark hysteresis, stall reporting and underrun
 * counting for BufferScheduler.
 *
 * Split out of BufferScheduler.ts (#5840). Both output paths (the AudioWorklet
 * feeder and the ScriptProcessorNode callback) share the one instance, so the
 * hysteresis lives in exactly one place and a stall has a single channel.
 *
 * @copyright (C) 2024 Auralis Team
 * @license AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
 */

import { PLAYBACK_ENGINE_CONFIG } from './audioConstants';

export class BufferHealth {
  private underrunCount: number = 0;
  private paused: boolean = false; // Track if we paused due to low buffer
  // True once the backend has delivered everything it will (stream end). The
  // water marks then no longer apply: nothing more is coming to refill above
  // the low mark, so holding output would strand the tail of the track.
  private streamEnded: boolean = false;
  private stalled: boolean = false; // Last stall state reported via onStallChange

  // Buffer health thresholds (in seconds of audio). Water marks stay below the
  // backend chunk interval (CHUNK_INTERVAL = 10 s) so a single late chunk does
  // not trigger an avoidable pause. See audioConstants.ts.
  private lowWaterMarkSeconds: number = PLAYBACK_ENGINE_CONFIG.lowWaterMarkSeconds;  // Pause when < 5 seconds buffered
  private highWaterMarkSeconds: number = PLAYBACK_ENGINE_CONFIG.highWaterMarkSeconds; // Resume when > 8 seconds buffered

  constructor(private onStallChange?: (stalled: boolean) => void) {}

  /** True while output is held for lack of buffered audio. */
  get isPaused(): boolean {
    return this.paused;
  }

  getUnderrunCount(): number {
    return this.underrunCount;
  }

  resetUnderrunCount(): void {
    this.underrunCount = 0;
  }

  /** Count a hard underrun. Returns the new total; the caller reports the stall. */
  countUnderrun(): number {
    this.underrunCount++;
    return this.underrunCount;
  }

  /**
   * The stream has delivered its last chunk. Play out whatever is buffered
   * instead of waiting for a refill to the high-water mark that cannot come —
   * otherwise the final seconds sit unplayed in the ring and the track never
   * reaches its end.
   */
  markStreamEnded(): void {
    this.streamEnded = true;
    this.paused = false;
  }

  /** Forget a previous stream's end (stop / seek restart the same engine). */
  resetStreamEnded(): void {
    this.streamEnded = false;
  }

  reset(): void {
    this.paused = false;
    this.setStalled(false);
  }

  /** Report a stall transition. Low-water pauses and hard underruns share this
   *  one channel so the UI has a single signal to follow (#5461). */
  setStalled(stalled: boolean): void {
    if (stalled === this.stalled) return;
    this.stalled = stalled;
    this.onStallChange?.(stalled);
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
  check(
    bufferedSeconds: number,
    context: 'feed' | 'playback',
    reportStall: boolean = true
  ): boolean {
    if (this.streamEnded) return true;

    if (!this.paused && bufferedSeconds < this.lowWaterMarkSeconds) {
      this.paused = true;
      if (reportStall) this.setStalled(true);
      console.warn(
        `[BufferScheduler] Buffer critically low (${bufferedSeconds.toFixed(1)}s < ${this.lowWaterMarkSeconds}s). ` +
        `Pausing ${context}...`
      );
      return false;
    }

    if (this.paused) {
      if (bufferedSeconds >= this.highWaterMarkSeconds) {
        this.paused = false;
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
}

export default BufferHealth;
