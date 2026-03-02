/**
 * Render Profiler Tests
 * ~~~~~~~~~~~~~~~~~~~~~
 *
 * Unit tests for component re-render profiling utilities.
 *
 * Test Coverage:
 * - Render time tracking
 * - Slow render detection
 * - Props change tracking
 * - Performance warnings
 * - Metrics aggregation
 *
 * Phase C.4b: Performance Optimization
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  renderMetricsStore,
  checkPerformanceWarnings,
  type RenderMetrics,
} from '../useRenderProfiler';

describe('Render Profiler', () => {
  beforeEach(() => {
    renderMetricsStore.reset();
  });

  // ============================================================================
  // Metrics Recording Tests
  // ============================================================================

  describe('Metrics Recording', () => {
    it('should record render metrics', () => {
      const componentName = 'TestComponent';
      renderMetricsStore.recordRender(componentName, 5.5, 2.3, 'mount', new Set());

      const metrics = renderMetricsStore.getMetrics(
        componentName
      ) as RenderMetrics;

      expect(metrics.component).toBe(componentName);
      expect(metrics.renderTime).toBe(5.5);
      expect(metrics.commitTime).toBe(2.3);
      expect(metrics.phase).toBe('mount');
      expect(metrics.count).toBe(1);
    });

    it('should track multiple renders', () => {
      const componentName = 'TestComponent';

      renderMetricsStore.recordRender(componentName, 5.0, 2.0, 'mount', new Set());
      renderMetricsStore.recordRender(
        componentName,
        6.0,
        2.5,
        'update',
        new Set()
      );
      renderMetricsStore.recordRender(
        componentName,
        4.0,
        1.8,
        'update',
        new Set()
      );

      const metrics = renderMetricsStore.getMetrics(
        componentName
      ) as RenderMetrics;

      expect(metrics.count).toBe(3);
      expect(metrics.averageRenderTime).toBe(5); // (5 + 6 + 4) / 3
    });

    it('should calculate average render time', () => {
      const componentName = 'TestComponent';

      renderMetricsStore.recordRender(componentName, 10.0, 2.0, 'mount', new Set());
      renderMetricsStore.recordRender(
        componentName,
        20.0,
        2.5,
        'update',
        new Set()
      );

      const metrics = renderMetricsStore.getMetrics(
        componentName
      ) as RenderMetrics;

      expect(metrics.averageRenderTime).toBe(15);
    });
  });

  // ============================================================================
  // Slow Render Detection Tests
  // ============================================================================

  describe('Slow Render Detection', () => {
    it('should track slow renders', () => {
      const componentName = 'SlowComponent';

      // Record a slow render (> 5ms default threshold)
      renderMetricsStore.recordRender(
        componentName,
        10.0,
        2.0,
        'update',
        new Set()
      );

      const metrics = renderMetricsStore.getMetrics(
        componentName
      ) as RenderMetrics;

      expect(metrics.slowRenders.length).toBe(1);
      expect(metrics.slowRenders[0].renderTime).toBe(10.0);
    });

    it('should not track fast renders as slow', () => {
      const componentName = 'FastComponent';

      renderMetricsStore.recordRender(componentName, 2.0, 1.0, 'mount', new Set());
      renderMetricsStore.recordRender(
        componentName,
        3.0,
        1.5,
        'update',
        new Set()
      );

      const metrics = renderMetricsStore.getMetrics(
        componentName
      ) as RenderMetrics;

      expect(metrics.slowRenders.length).toBe(0);
    });

    it('should limit slow renders history to 10', () => {
      const componentName = 'VerySlowComponent';

      // Record 15 slow renders
      for (let i = 0; i < 15; i++) {
        renderMetricsStore.recordRender(
          componentName,
          10.0 + i,
          2.0,
          'update',
          new Set()
        );
      }

      const metrics = renderMetricsStore.getMetrics(
        componentName
      ) as RenderMetrics;

      expect(metrics.slowRenders.length).toBe(10);
      // Should keep the last 10 renders
      expect(metrics.slowRenders[0].renderTime).toBe(15.0);
      expect(metrics.slowRenders[9].renderTime).toBe(24.0);
    });

    it('should identify slowest components', () => {
      renderMetricsStore.recordRender('Component1', 3.0, 1.0, 'mount', new Set());
      renderMetricsStore.recordRender('Component2', 8.0, 2.0, 'mount', new Set());
      renderMetricsStore.recordRender('Component3', 5.0, 1.5, 'mount', new Set());

      const slowest = renderMetricsStore.getSlowestComponents(2);

      expect(slowest.length).toBe(2);
      expect(slowest[0].component).toBe('Component2');
      expect(slowest[1].component).toBe('Component3');
    });

    it('should identify slowest renders', () => {
      renderMetricsStore.recordRender('Comp1', 3.0, 1.0, 'mount', new Set());
      renderMetricsStore.recordRender('Comp2', 15.0, 2.0, 'mount', new Set());
      renderMetricsStore.recordRender('Comp3', 12.0, 1.5, 'mount', new Set());

      const slowest = renderMetricsStore.getSlowestRenders(2);

      expect(slowest.length).toBe(2);
      expect(slowest[0].renderTime).toBe(15.0);
      expect(slowest[1].renderTime).toBe(12.0);
    });
  });

  // ============================================================================
  // Metrics Retrieval Tests
  // ============================================================================

  describe('Metrics Retrieval', () => {
    it('should get metrics for specific component', () => {
      renderMetricsStore.recordRender('Component1', 5.0, 2.0, 'mount', new Set());

      const metrics = renderMetricsStore.getMetrics('Component1') as RenderMetrics;

      expect(metrics.component).toBe('Component1');
    });

    it('should get all metrics', () => {
      renderMetricsStore.recordRender('Component1', 5.0, 2.0, 'mount', new Set());
      renderMetricsStore.recordRender('Component2', 6.0, 2.5, 'mount', new Set());

      const allMetrics = renderMetricsStore.getMetrics() as RenderMetrics[];

      expect(allMetrics.length).toBe(2);
      expect(allMetrics.map((m) => m.component)).toContain('Component1');
      expect(allMetrics.map((m) => m.component)).toContain('Component2');
    });

    it('should return empty metric for unknown component', () => {
      const metrics = renderMetricsStore.getMetrics(
        'UnknownComponent'
      ) as RenderMetrics;

      expect(metrics.component).toBe('UnknownComponent');
      expect(metrics.count).toBe(0);
      expect(metrics.averageRenderTime).toBe(0);
    });
  });

  // ============================================================================
  // Reset Tests
  // ============================================================================

  describe('Reset', () => {
    it('should reset specific component metrics', () => {
      renderMetricsStore.recordRender('Component1', 5.0, 2.0, 'mount', new Set());
      renderMetricsStore.recordRender('Component2', 6.0, 2.5, 'mount', new Set());

      renderMetricsStore.reset('Component1');

      const allMetrics = renderMetricsStore.getMetrics() as RenderMetrics[];
      expect(allMetrics.map((m) => m.component)).not.toContain('Component1');
      expect(allMetrics.map((m) => m.component)).toContain('Component2');
    });

    it('should reset all metrics', () => {
      renderMetricsStore.recordRender('Component1', 5.0, 2.0, 'mount', new Set());
      renderMetricsStore.recordRender('Component2', 6.0, 2.5, 'mount', new Set());

      renderMetricsStore.reset();

      const allMetrics = renderMetricsStore.getMetrics() as RenderMetrics[];
      expect(allMetrics.length).toBe(0);
    });
  });

  // ============================================================================
  // Report Generation Tests
  // ============================================================================

  describe('Report Generation', () => {
    it('should generate report for empty metrics', () => {
      const report = renderMetricsStore.report();
      expect(report).toContain('No render metrics recorded');
    });

    it('should generate report with metrics', () => {
      renderMetricsStore.recordRender(
        'TestComponent',
        5.0,
        2.0,
        'mount',
        new Set()
      );

      const report = renderMetricsStore.report();

      expect(report).toContain('TestComponent');
      expect(report).toContain('Renders: 1');
      expect(report).toContain('5.000ms');
    });

    it('should include slowest components in report', () => {
      renderMetricsStore.recordRender('SlowComponent', 15.0, 2.0, 'mount', new Set());
      renderMetricsStore.recordRender('FastComponent', 2.0, 1.0, 'mount', new Set());

      const report = renderMetricsStore.report();

      expect(report).toContain('Slowest Components');
      expect(report).toContain('SlowComponent');
    });
  });

  // ============================================================================
  // Performance Warnings Tests
  // ============================================================================

  describe('Performance Warnings', () => {
    it('should warn on slow renders', () => {
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      renderMetricsStore.recordRender(
        'SlowComponent',
        15.0,
        2.0,
        'mount',
        new Set()
      );

      checkPerformanceWarnings({ warning: 10, critical: 20 });

      expect(warnSpy).toHaveBeenCalled();
      warnSpy.mockRestore();
    });

    it('should error on critical renders', () => {
      const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      renderMetricsStore.recordRender(
        'CriticalComponent',
        25.0,
        2.0,
        'mount',
        new Set()
      );

      checkPerformanceWarnings({ warning: 10, critical: 20 });

      expect(errorSpy).toHaveBeenCalled();
      errorSpy.mockRestore();
    });

    it('should not warn on fast renders', () => {
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      renderMetricsStore.recordRender(
        'FastComponent',
        3.0,
        1.0,
        'mount',
        new Set()
      );

      checkPerformanceWarnings({ warning: 10, critical: 20 });

      expect(warnSpy).not.toHaveBeenCalled();
      warnSpy.mockRestore();
    });
  });
});
