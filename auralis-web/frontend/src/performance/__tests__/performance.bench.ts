/**
 * Performance Benchmarks
 * ~~~~~~~~~~~~~~~~~~~~~
 *
 * Benchmark tests for measuring performance of selectors, components, and utilities.
 * Helps identify performance regressions and optimization opportunities.
 *
 * Test Coverage:
 * - Selector performance
 * - Component render performance
 * - Memoization effectiveness
 * - Bundle operations
 *
 * Phase C.4b: Performance Optimization
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { shallowEqual, deepEqual, compareProps } from '../withMemo';
import { renderMetricsStore } from '../useRenderProfiler';
import { bundleAnalyzer } from '../bundleAnalyzer';
import type { ModuleMetrics } from '../bundleAnalyzer';

describe('Performance Benchmarks', () => {
  // ============================================================================
  // Selector Performance Benchmarks
  // ============================================================================

  describe('Selector Performance', () => {
    it('should perform shallow equality in < 1ms for small objects', () => {
      const obj1 = { a: 1, b: 2, c: 3, d: 4, e: 5 };
      const obj2 = { a: 1, b: 2, c: 3, d: 4, e: 5 };

      const startTime = performance.now();
      for (let i = 0; i < 10000; i++) {
        shallowEqual(obj1, obj2);
      }
      const duration = performance.now() - startTime;

      expect(duration).toBeLessThan(10); // Should be very fast
    });

    it('should detect inequality quickly', () => {
      const obj1 = { a: 1, b: 2, c: 3, d: 4, e: 5 };
      const obj2 = { a: 1, b: 2, c: 3, d: 4, e: 999 };

      const startTime = performance.now();
      for (let i = 0; i < 10000; i++) {
        shallowEqual(obj1, obj2);
      }
      const duration = performance.now() - startTime;

      expect(duration).toBeLessThan(10);
    });

    it('should handle deep objects efficiently', () => {
      const deepObj1 = {
        level1: {
          level2: {
            level3: {
              level4: {
                value: 1,
              },
            },
          },
        },
      };

      const deepObj2 = {
        level1: {
          level2: {
            level3: {
              level4: {
                value: 1,
              },
            },
          },
        },
      };

      const startTime = performance.now();
      for (let i = 0; i < 1000; i++) {
        deepEqual(deepObj1, deepObj2);
      }
      const duration = performance.now() - startTime;

      expect(duration).toBeLessThan(50);
    });

    it('should filter props efficiently', () => {
      const props = { a: 1, b: 2, c: 3, d: 4, e: 5 };
      const comparison = compareProps(['a', 'b']);

      const startTime = performance.now();
      for (let i = 0; i < 10000; i++) {
        comparison(props, props);
      }
      const duration = performance.now() - startTime;

      expect(duration).toBeLessThan(10);
    });
  });

  // ============================================================================
  // Component Render Benchmarks
  // ============================================================================

  describe('Component Render Benchmarks', () => {
    beforeEach(() => {
      renderMetricsStore.reset();
    });

    it('should track fast renders (< 5ms)', () => {
      const componentName = 'FastComponent';

      // Record 100 fast renders
      for (let i = 0; i < 100; i++) {
        renderMetricsStore.recordRender(componentName, 2.5, 1.0, 'update', new Set());
      }

      const metrics = renderMetricsStore.getMetrics(componentName);
      expect(metrics).not.toBeNull();
      expect((metrics as any).averageRenderTime).toBeLessThan(5);
    });

    it('should identify slow renders efficiently', () => {
      const startTime = performance.now();

      // Record many renders
      for (let i = 0; i < 1000; i++) {
        renderMetricsStore.recordRender(
          `Component${i % 10}`,
          Math.random() * 20,
          Math.random() * 5,
          'update',
          new Set()
        );
      }

      const slowest = renderMetricsStore.getSlowestComponents(10);
      const duration = performance.now() - startTime;

      expect(slowest.length).toBeLessThanOrEqual(10);
      expect(duration).toBeLessThan(50); // Should be quick
    });

    it('should aggregate metrics efficiently', () => {
      // Record many component renders
      const startTime = performance.now();

      for (let componentNum = 0; componentNum < 50; componentNum++) {
        for (let render = 0; render < 100; render++) {
          renderMetricsStore.recordRender(
            `Component${componentNum}`,
            Math.random() * 10,
            Math.random() * 3,
            'update',
            new Set()
          );
        }
      }

      const duration = performance.now() - startTime;
      const metrics = renderMetricsStore.getMetrics() as any[];

      expect(metrics.length).toBe(50);
      expect(duration).toBeLessThan(100);
    });
  });

  // ============================================================================
  // Bundle Analysis Benchmarks
  // ============================================================================

  describe('Bundle Analysis Benchmarks', () => {
    beforeEach(() => {
      bundleAnalyzer.reset();
    });

    it('should analyze large bundles quickly', () => {
      const modules: ModuleMetrics[] = Array.from({ length: 1000 }, (_, i) => ({
        name: `module-${i}`,
        size: Math.random() * 100000,
        gzipSize: Math.random() * 50000,
        isDuplicate: i % 50 === 0,
        dependents: Array.from({ length: Math.random() * 10 }, (_, j) =>
          `component-${j}`
        ),
        dependencies: [],
        isChunk: i % 20 === 0,
      }));

      bundleAnalyzer.recordMetrics(modules);

      const startTime = performance.now();
      const analysis = bundleAnalyzer.analyzeBundle();
      const duration = performance.now() - startTime;

      expect(analysis.metrics.moduleCount).toBe(1000);
      expect(duration).toBeLessThan(100);
    });

    it('should identify largest modules quickly', () => {
      const modules: ModuleMetrics[] = Array.from({ length: 500 }, (_, i) => ({
        name: `module-${i}`,
        size: Math.random() * 100000,
        gzipSize: Math.random() * 50000,
        isDuplicate: false,
        dependents: [],
        dependencies: [],
        isChunk: false,
      }));

      bundleAnalyzer.recordMetrics(modules);

      const startTime = performance.now();
      const largest = bundleAnalyzer.getLargestModules(20);
      const duration = performance.now() - startTime;

      expect(largest.length).toBeLessThanOrEqual(20);
      expect(duration).toBeLessThan(10);
    });

    it('should generate reports quickly', () => {
      const modules: ModuleMetrics[] = Array.from({ length: 100 }, (_, i) => ({
        name: `module-${i}`,
        size: Math.random() * 100000,
        gzipSize: Math.random() * 50000,
        isDuplicate: false,
        dependents: [],
        dependencies: [],
        isChunk: false,
      }));

      bundleAnalyzer.recordMetrics(modules);

      const startTime = performance.now();
      const report = bundleAnalyzer.generateReport();
      const duration = performance.now() - startTime;

      expect(report).toBeTruthy();
      expect(duration).toBeLessThan(50);
    });
  });

  // ============================================================================
  // Memory Usage Benchmarks
  // ============================================================================

  describe('Memory Usage', () => {
    it('should handle large metric sets without excessive memory', () => {
      // This is a basic test - real memory testing would use HeapSnapshot API
      const modules: ModuleMetrics[] = Array.from({ length: 10000 }, (_, i) => ({
        name: `module-${i}`,
        size: Math.random() * 100000,
        gzipSize: Math.random() * 50000,
        isDuplicate: false,
        dependents: [],
        dependencies: [],
        isChunk: false,
      }));

      // Record metrics shouldn't cause issues
      bundleAnalyzer.recordMetrics(modules);

      const metrics = bundleAnalyzer.getCurrentMetrics();
      expect(metrics).not.toBeNull();
    });
  });

  // ============================================================================
  // Memoization Effectiveness Benchmarks
  // ============================================================================

  describe('Memoization Effectiveness', () => {
    it('should demonstrate shallow equality benefits', () => {
      const obj = { a: 1, b: 2, c: 3, d: 4, e: 5 };

      // Measure without memoization (always recompute)
      const startNoMemo = performance.now();
      for (let i = 0; i < 10000; i++) {
        JSON.stringify(obj); // Simulates computation
      }
      const durationNoMemo = performance.now() - startNoMemo;

      // Measure with memoization (cached)
      const startMemo = performance.now();
      let cached = JSON.stringify(obj);
      for (let i = 0; i < 10000; i++) {
        if (shallowEqual(obj, obj)) {
          // Use cached value
          cached;
        }
      }
      const durationMemo = performance.now() - startMemo;

      // Memoization should be faster
      expect(durationMemo).toBeLessThan(durationNoMemo);
    });
  });

  // ============================================================================
  // Threshold Tests
  // ============================================================================

  describe('Performance Thresholds', () => {
    it('should keep selector performance under 1ms per call', () => {
      const props = { a: 1, b: 2, c: 3, d: 4, e: 5 };
      const comparison = compareProps(['a', 'b', 'c']);

      const startTime = performance.now();
      for (let i = 0; i < 1000; i++) {
        comparison(props, props);
      }
      const avgTime = (performance.now() - startTime) / 1000;

      expect(avgTime).toBeLessThan(1);
    });

    it('should keep component metrics recording under 0.1ms per call', () => {
      const startTime = performance.now();

      for (let i = 0; i < 1000; i++) {
        renderMetricsStore.recordRender(
          'Component',
          Math.random() * 10,
          Math.random() * 5,
          'update',
          new Set()
        );
      }

      const avgTime = (performance.now() - startTime) / 1000;

      expect(avgTime).toBeLessThan(0.1);
    });

    it('should keep bundle analysis under 50ms for large bundles', () => {
      const modules: ModuleMetrics[] = Array.from({ length: 2000 }, (_, i) => ({
        name: `module-${i}`,
        size: Math.random() * 100000,
        gzipSize: Math.random() * 50000,
        isDuplicate: i % 100 === 0,
        dependents: Array.from({ length: Math.floor(Math.random() * 5) }, (_, j) =>
          `component-${j}`
        ),
        dependencies: [],
        isChunk: i % 50 === 0,
      }));

      bundleAnalyzer.recordMetrics(modules);

      const startTime = performance.now();
      bundleAnalyzer.analyzeBundle();
      const duration = performance.now() - startTime;

      expect(duration).toBeLessThan(50);
    });
  });
});
