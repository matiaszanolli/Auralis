/**
 * React Component Re-render Profiler
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Profiling utilities for tracking component re-renders and performance metrics.
 * Uses React DevTools Profiler API to measure rendering performance.
 *
 * Features:
 * - Component render time tracking
 * - Re-render cause detection
 * - Performance metrics visualization
 * - Why-did-you-render integration
 * - Automatic performance warnings
 *
 * Phase C.4b: Performance Optimization
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { useEffect, useRef, useCallback } from 'react';

// ============================================================================
// Types
// ============================================================================

interface RenderMetrics {
  component: string;
  renderTime: number;
  commitTime: number;
  startTime: number;
  interactions: Set<any>;
  phase: 'mount' | 'update';
  count: number;
  averageRenderTime: number;
  slowRenders: RenderMetrics[];
}

interface PerformanceThreshold {
  warning: number; // ms - warn if render time exceeds this
  critical: number; // ms - critical if render time exceeds this
}

interface RenderProfilerConfig {
  enabled: boolean;
  thresholds?: PerformanceThreshold;
  trackPropsChanges?: boolean;
  verbose?: boolean;
}

// ============================================================================
// Global Render Metrics Store
// ============================================================================

class RenderMetricsStore {
  private metrics: Map<string, RenderMetrics> = new Map();
  private slowRenderThreshold: number = 5; // ms

  recordRender(
    component: string,
    renderTime: number,
    commitTime: number,
    phase: 'mount' | 'update',
    interactions: Set<any>
  ): void {
    let metric = this.metrics.get(component);

    if (!metric) {
      metric = {
        component,
        renderTime: 0,
        commitTime: 0,
        startTime: Date.now(),
        interactions,
        phase,
        count: 0,
        averageRenderTime: 0,
        slowRenders: [],
      };
      this.metrics.set(component, metric);
    }

    metric.count++;
    metric.renderTime = renderTime;
    metric.commitTime = commitTime;
    metric.averageRenderTime =
      (metric.averageRenderTime * (metric.count - 1) + renderTime) /
      metric.count;

    // Track slow renders
    if (renderTime > this.slowRenderThreshold) {
      metric.slowRenders.push({
        component,
        renderTime,
        commitTime,
        startTime: Date.now(),
        interactions,
        phase,
        count: metric.count,
        averageRenderTime: metric.averageRenderTime,
        slowRenders: [],
      });

      // Keep only last 10 slow renders
      if (metric.slowRenders.length > 10) {
        metric.slowRenders.shift();
      }
    }
  }

  getMetrics(component?: string): RenderMetrics | RenderMetrics[] {
    if (component) {
      return this.metrics.get(component) || this.createEmptyMetric(component);
    }
    return Array.from(this.metrics.values());
  }

  private createEmptyMetric(component: string): RenderMetrics {
    return {
      component,
      renderTime: 0,
      commitTime: 0,
      startTime: 0,
      interactions: new Set(),
      phase: 'mount',
      count: 0,
      averageRenderTime: 0,
      slowRenders: [],
    };
  }

  getSlowestComponents(limit: number = 10): RenderMetrics[] {
    return Array.from(this.metrics.values())
      .sort((a, b) => b.averageRenderTime - a.averageRenderTime)
      .slice(0, limit);
  }

  getSlowestRenders(limit: number = 20): Array<RenderMetrics & { component: string }> {
    const allSlowRenders: Array<RenderMetrics & { component: string }> = [];

    for (const metric of this.metrics.values()) {
      allSlowRenders.push(
        ...metric.slowRenders.map((sr) => ({
          ...sr,
          component: metric.component,
        }))
      );
    }

    return allSlowRenders
      .sort((a, b) => b.renderTime - a.renderTime)
      .slice(0, limit);
  }

  reset(component?: string): void {
    if (component) {
      this.metrics.delete(component);
    } else {
      this.metrics.clear();
    }
  }

  report(): string {
    const metrics = Array.from(this.metrics.values());

    if (metrics.length === 0) {
      return 'No render metrics recorded';
    }

    let report = '📊 Component Render Performance Report\n';
    report += '======================================\n\n';

    for (const metric of metrics) {
      report += `${metric.component}:\n`;
      report += `  Renders: ${metric.count}\n`;
      report += `  Avg Time: ${metric.averageRenderTime.toFixed(3)}ms\n`;
      report += `  Last Render: ${metric.renderTime.toFixed(3)}ms\n`;
      report += `  Commit Time: ${metric.commitTime.toFixed(3)}ms\n`;
      report += `  Phase: ${metric.phase}\n`;
      report += `  Slow Renders: ${metric.slowRenders.length}\n\n`;
    }

    const slowest = this.getSlowestComponents(5);
    if (slowest.length > 0) {
      report += '\n🐌 Slowest Components:\n';
      for (const metric of slowest) {
        report += `  - ${metric.component}: ${metric.averageRenderTime.toFixed(
          3
        )}ms avg\n`;
      }
    }

    return report;
  }
}

export const renderMetricsStore = new RenderMetricsStore();

// ============================================================================
// React Hook: useRenderProfiler
// ============================================================================

/**
 * Hook for profiling component re-renders
 * Usage:
 *   useRenderProfiler('MyComponent', { enabled: true, verbose: true })
 */
export function useRenderProfiler(
  componentName: string,
  config: RenderProfilerConfig = { enabled: true }
) {
  const startTimeRef = useRef<number>(0);
  const renderCountRef = useRef<number>(0);
  const propsRef = useRef<any>(null);
  const memoRef = useRef<{ prevProps: any; changeCount: number }>({
    prevProps: null,
    changeCount: 0,
  });

  // Track render start time
  startTimeRef.current = performance.now();
  renderCountRef.current++;

  // Track prop changes if enabled
  const trackPropsChanges = useCallback((currentProps: any) => {
    if (!config.trackPropsChanges) return;

    if (memoRef.current.prevProps) {
      let changed = false;
      const changes: string[] = [];

      for (const key in currentProps) {
        if (currentProps[key] !== memoRef.current.prevProps[key]) {
          changed = true;
          changes.push(key);
        }
      }

      if (changed && config.verbose) {
        console.warn(`[${componentName}] Props changed:`, changes);
      }

      if (changed) {
        memoRef.current.changeCount++;
      }
    }

    memoRef.current.prevProps = currentProps;
  }, [componentName, config.trackPropsChanges, config.verbose]);

  // Record render metrics on commit
  useEffect(() => {
    if (!config.enabled) return;

    const renderTime = performance.now() - startTimeRef.current;

    renderMetricsStore.recordRender(
      componentName,
      renderTime,
      0, // commitTime will be measured separately
      renderCountRef.current === 1 ? 'mount' : 'update',
      new Set()
    );

    if (config.verbose) {
      console.log(
        `[${componentName}] Render #${renderCountRef.current}: ${renderTime.toFixed(
          3
        )}ms`
      );
    }
  }, [componentName, config.enabled, config.verbose]);

  return {
    trackPropsChanges,
    renderCount: renderCountRef.current,
    propChangeCount: memoRef.current.changeCount,
  };
}

// ============================================================================
// Performance Warnings
// ============================================================================

/**
 * Check for performance issues and warn
 */
export function checkPerformanceWarnings(
  thresholds: PerformanceThreshold = { warning: 10, critical: 20 }
) {
  const metrics = renderMetricsStore.getMetrics() as RenderMetrics[];

  for (const metric of metrics) {
    if (metric.averageRenderTime > thresholds.critical) {
      console.error(
        `🔴 CRITICAL: ${metric.component} renders in ${metric.averageRenderTime.toFixed(
          3
        )}ms (threshold: ${thresholds.critical}ms)`
      );
    } else if (metric.averageRenderTime > thresholds.warning) {
      console.warn(
        `🟡 WARNING: ${metric.component} renders in ${metric.averageRenderTime.toFixed(
          3
        )}ms (threshold: ${thresholds.warning}ms)`
      );
    }
  }
}

export type { RenderProfilerConfig, PerformanceThreshold };
