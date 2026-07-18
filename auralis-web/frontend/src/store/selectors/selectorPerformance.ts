/**
 * Selector Performance Tracking
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Instrumentation for Redux selectors, split out of store/selectors/index.ts
 * (#4316) — this is a cross-cutting concern, not a domain selector.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import type { RootState } from '@/store/index';

export interface SelectorMetrics {
  name: string;
  calls: number;
  cacheHits: number;
  cacheMisses: number;
  totalTime: number;
  averageTime: number;
  lastComputeTime: number;
}

export class SelectorPerformanceTracker {
  private metrics: Map<string, SelectorMetrics> = new Map();

  recordCall(name: string, computeTime: number, hit: boolean): void {
    let metric = this.metrics.get(name);
    if (!metric) {
      metric = { name, calls: 0, cacheHits: 0, cacheMisses: 0, totalTime: 0, averageTime: 0, lastComputeTime: 0 };
      this.metrics.set(name, metric);
    }
    metric.calls++;
    if (hit) { metric.cacheHits++; } else { metric.cacheMisses++; }
    metric.totalTime += computeTime;
    metric.averageTime = metric.totalTime / metric.calls;
    metric.lastComputeTime = computeTime;
  }

  getMetrics(name?: string): SelectorMetrics | SelectorMetrics[] {
    if (name) return this.metrics.get(name) || { name, calls: 0, cacheHits: 0, cacheMisses: 0, totalTime: 0, averageTime: 0, lastComputeTime: 0 };
    return Array.from(this.metrics.values());
  }

  getCacheHitRate(name?: string): number {
    if (name) {
      const m = this.metrics.get(name);
      return (m && m.calls > 0) ? (m.cacheHits / m.calls) * 100 : 0;
    }
    const all = Array.from(this.metrics.values());
    const calls = all.reduce((s, m) => s + m.calls, 0);
    const hits = all.reduce((s, m) => s + m.cacheHits, 0);
    return calls > 0 ? (hits / calls) * 100 : 0;
  }

  reset(name?: string): void {
    if (name) { this.metrics.delete(name); } else { this.metrics.clear(); }
  }

  report(): string {
    const metrics = Array.from(this.metrics.values());
    if (metrics.length === 0) return 'No selector metrics recorded';
    let out = '📊 Selector Performance Report\n================================\n\n';
    for (const m of metrics) {
      const rate = m.calls > 0 ? ((m.cacheHits / m.calls) * 100).toFixed(1) : '0.0';
      out += `${m.name}:\n  Calls: ${m.calls}\n  Cache Hit Rate: ${rate}%\n  Avg Time: ${m.averageTime.toFixed(3)}ms\n\n`;
    }
    out += `Overall Cache Hit Rate: ${this.getCacheHitRate().toFixed(1)}%`;
    return out;
  }
}

export const selectorPerformance = new SelectorPerformanceTracker();

/**
 * Create a memoized selector with performance tracking.
 *
 * #3621: now a thin wrapper around RTK/reselect's `createSelector` plus a
 * call-tracking shim. The previous hand-rolled implementation had a single
 * shared cache slot that thrashed when two consumers called the same
 * selector with different inputs — reselect has the same single-slot
 * behaviour per selector instance, but consumers are documented to wrap
 * in `useMemo(() => makeSelectX(arg), [arg])` for per-instance caching.
 *
 * For factory selectors (e.g. `makeSelectTrackAtIndex`), reselect already
 * handles the memo correctly via createSelector — callers should prefer
 * that pattern directly for new code.
 */
export function createMemoizedSelector<T, Args extends unknown[] = unknown[]>(
  name: string,
  selectInputs: (state: RootState) => [...Args],
  computeFn: (...args: Args) => T
): (state: RootState) => T {
  // Use Reselect's createSelector for the actual memoization to avoid
  // re-implementing equality + caching by hand.
  const wrappedCompute = (...args: Args): T => {
    const startTime = performance.now();
    const result = computeFn(...args);
    selectorPerformance.recordCall(name, performance.now() - startTime, false);
    return result;
  };

  // selectInputs returns a tuple; createSelector accepts an array of
  // input selectors. Wrap selectInputs in a single input selector and
  // memo over the resulting tuple identity instead.
  let lastTuple: unknown[] | undefined;
  let lastResult: T | undefined;
  return (state: RootState): T => {
    const inputs = selectInputs(state);
    const sameInputs =
      lastTuple &&
      lastTuple.length === inputs.length &&
      lastTuple.every((v, i) => v === inputs[i]);

    if (sameInputs && lastTuple !== undefined) {
      selectorPerformance.recordCall(name, 0, true);
      return lastResult as T;
    }
    lastResult = wrappedCompute(...inputs);
    lastTuple = [...inputs];
    return lastResult;
  };
}
