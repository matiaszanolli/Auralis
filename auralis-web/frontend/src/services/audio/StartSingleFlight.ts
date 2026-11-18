/**
 * StartSingleFlight - the single-flight / cancellation bookkeeping of AudioPlaybackEngine.startPlayback.
 *
 * A start awaits a context resume and a worklet load. Chunks landing inside that window each ask
 * to start and share one attempt (#6043); a stop/dispose/pause inside it cancels the attempt. A
 * cancelled attempt stays pending until its awaits finish, so it is never handed to a caller
 * wanting a fresh start (#6424).
 */
export class StartSingleFlight {
  private attempt = 0;
  private flight: { attempt: number; promise: Promise<void> } | null = null;

  /** Run `start` unless a current-attempt start is already in flight, in which case share it. */
  run(start: (attempt: number) => Promise<void>): Promise<void> {
    const current = this.flight;
    if (current && current.attempt === this.attempt) return current.promise;
    const attempt = this.attempt;
    const promise: Promise<void> = start(attempt).finally(() => {
      if (this.flight?.promise === promise) this.flight = null;
    });
    this.flight = { attempt, promise };
    return promise;
  }

  /** True once `attempt` was cancelled; a start checks this after each await. */
  isStale(attempt: number): boolean {
    return attempt !== this.attempt;
  }

  /** Cancel any in-flight attempt (stop/dispose). */
  cancel(): void {
    this.attempt += 1;
  }

  /** Cancel only if a start is in flight (pause): there is nothing to cancel otherwise. */
  cancelPending(): void {
    if (this.flight) this.attempt += 1;
  }
}
