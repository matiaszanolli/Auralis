/**
 * AdaptiveTimeoutManager - Dynamically adjusts chunk loading timeouts
 *
 * Responsibility: Track chunk loading times and calculate adaptive timeouts
 * based on actual system performance.
 *
 * Strategy:
 * - Measure actual chunk load times (100ms to 2000ms typically)
 * - Calculate 95th percentile latency from recent samples
 * - Set timeout = 95th percentile × 1.5 safety margin
 * - Auto-tune every 20 chunks or on significant deviation
 * - Minimum 5s, maximum 30s timeout
 *
 * Benefits:
 * - Eliminates arbitrary 30s timeout
 * - Adapts to network conditions and CPU load
 * - Prevents timeout errors on slow systems
 * - Faster detection of actual failures
 */

interface LoadTimeSample {
  chunkIndex: number;
  latencyMs: number;
  timestamp: number;
}

export class AdaptiveTimeoutManager {
  private loadTimeSamples: LoadTimeSample[] = [];
  private currentTimeoutMs: number = 15000; // Start with 15s
  private readonly MIN_TIMEOUT_MS = 5000;
  private readonly MAX_TIMEOUT_MS = 30000;
  private readonly SAFETY_MARGIN = 1.5; // 50% safety margin
  private readonly PERCENTILE = 95; // Use 95th percentile
  private readonly SAMPLE_HISTORY_SIZE = 100; // Keep last 100 samples
  private readonly RETUNE_INTERVAL = 20; // Retune every 20 chunks
  private chunksSinceRetune = 0;
  private debug: (msg: string) => void = () => {};

  constructor(debugFn?: (msg: string) => void) {
    if (debugFn) {
      this.debug = debugFn;
    }
    this.debug('[TIMEOUT] AdaptiveTimeoutManager initialized');
  }

  /**
   * Record a chunk load time
   */
  recordChunkLoad(chunkIndex: number, latencyMs: number): void {
    this.loadTimeSamples.push({
      chunkIndex,
      latencyMs,
      timestamp: Date.now()
    });

    // Keep only recent samples
    if (this.loadTimeSamples.length > this.SAMPLE_HISTORY_SIZE) {
      this.loadTimeSamples.shift();
    }

    this.chunksSinceRetune++;

    // Retune timeout if needed
    if (this.chunksSinceRetune >= this.RETUNE_INTERVAL && this.loadTimeSamples.length >= 10) {
      this.retuneTimeout();
      this.chunksSinceRetune = 0;
    }
  }

  /**
   * Recalculate timeout based on recent load times
   */
  private retuneTimeout(): void {
    if (this.loadTimeSamples.length < 5) {
      return; // Not enough samples
    }

    // Get sorted latencies
    const latencies = this.loadTimeSamples
      .map(s => s.latencyMs)
      .sort((a, b) => a - b);

    // Calculate percentile (95th)
    const percentileIndex = Math.ceil((this.PERCENTILE / 100) * latencies.length) - 1;
    const percentileLatency = latencies[Math.max(0, percentileIndex)];

    // Calculate new timeout with safety margin
    const newTimeout = Math.ceil(percentileLatency * this.SAFETY_MARGIN);

    // Clamp to min/max
    const clampedTimeout = Math.max(
      this.MIN_TIMEOUT_MS,
      Math.min(this.MAX_TIMEOUT_MS, newTimeout)
    );

    // Only update if changed significantly (>10%)
    const changePercent = Math.abs(clampedTimeout - this.currentTimeoutMs) / this.currentTimeoutMs;
    if (changePercent > 0.1) {
      const oldTimeout = this.currentTimeoutMs;
      this.currentTimeoutMs = clampedTimeout;

      const avgLatency = Math.round(
        this.loadTimeSamples.reduce((sum, s) => sum + s.latencyMs, 0) /
        this.loadTimeSamples.length
      );

      this.debug(
        `[TIMEOUT] Retuned: ${oldTimeout}ms → ${clampedTimeout}ms ` +
        `(p95: ${Math.round(percentileLatency)}ms, avg: ${avgLatency}ms, samples: ${this.loadTimeSamples.length})`
      );
    }
  }

  /**
   * Get current adaptive timeout in milliseconds
   */
  getTimeoutMs(): number {
    return this.currentTimeoutMs;
  }

  /**
   * Get timeout in seconds (for display/logging)
   */
  getTimeoutSeconds(): number {
    return this.currentTimeoutMs / 1000;
  }

  /**
   * Get performance statistics
   */
  getStats() {
    if (this.loadTimeSamples.length === 0) {
      return {
        sampleCount: 0,
        currentTimeoutMs: this.currentTimeoutMs,
        averageLatencyMs: 0,
        minLatencyMs: 0,
        maxLatencyMs: 0
      };
    }

    const latencies = this.loadTimeSamples.map(s => s.latencyMs);
    const sum = latencies.reduce((a, b) => a + b, 0);

    return {
      sampleCount: this.loadTimeSamples.length,
      currentTimeoutMs: this.currentTimeoutMs,
      averageLatencyMs: Math.round(sum / latencies.length),
      minLatencyMs: Math.min(...latencies),
      maxLatencyMs: Math.max(...latencies)
    };
  }

  /**
   * Reset timeout and samples (e.g., on network change or track change)
   */
  reset(): void {
    this.loadTimeSamples = [];
    this.currentTimeoutMs = 15000; // Reset to 15s default
    this.chunksSinceRetune = 0;
    this.debug('[TIMEOUT] Reset to default (15s)');
  }

  /**
   * Clear old samples (older than maxAgeMs)
   */
  clearOldSamples(maxAgeMs: number = 60000): void {
    const cutoffTime = Date.now() - maxAgeMs;
    const beforeCount = this.loadTimeSamples.length;

    this.loadTimeSamples = this.loadTimeSamples.filter(s => s.timestamp > cutoffTime);

    if (beforeCount !== this.loadTimeSamples.length) {
      this.debug(
        `[TIMEOUT] Cleared ${beforeCount - this.loadTimeSamples.length} ` +
        `old samples (older than ${maxAgeMs}ms)`
      );
    }
  }
}

// Export singleton instance for use across the app
export const adaptiveTimeoutManager = new AdaptiveTimeoutManager();
