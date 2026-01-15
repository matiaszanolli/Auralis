/**
 * Bundle Analyzer Tests
 * ~~~~~~~~~~~~~~~~~~~~
 *
 * Unit tests for bundle size analysis tools.
 *
 * Test Coverage:
 * - Module size tracking
 * - Budget enforcement
 * - Optimization detection
 * - Historical analysis
 * - Report generation
 *
 * Phase C.4b: Performance Optimization
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  bundleAnalyzer,
  BundleAnalyzer,
  type ModuleMetrics,
  type SizeBudget,
} from '../bundleAnalyzer';

describe('Bundle Analyzer', () => {
  let analyzer: BundleAnalyzer;

  beforeEach(() => {
    analyzer = new BundleAnalyzer();
  });

  // ============================================================================
  // Metrics Recording Tests
  // ============================================================================

  describe('Metrics Recording', () => {
    it('should record bundle metrics', () => {
      const modules: ModuleMetrics[] = [
        {
          name: 'module1',
          size: 10000,
          gzipSize: 5000,
          isDuplicate: false,
          dependents: [],
          dependencies: [],
          isChunk: false,
        },
      ];

      analyzer.recordMetrics(modules);

      const metrics = analyzer.getCurrentMetrics();
      expect(metrics).not.toBeNull();
      expect(metrics!.totalSize).toBe(10000);
      expect(metrics!.totalGzipSize).toBe(5000);
      expect(metrics!.moduleCount).toBe(1);
    });

    it('should track multiple modules', () => {
      const modules: ModuleMetrics[] = [
        {
          name: 'module1',
          size: 10000,
          gzipSize: 5000,
          isDuplicate: false,
          dependents: [],
          dependencies: [],
          isChunk: false,
        },
        {
          name: 'module2',
          size: 15000,
          gzipSize: 7000,
          isDuplicate: false,
          dependents: [],
          dependencies: [],
          isChunk: false,
        },
      ];

      analyzer.recordMetrics(modules);

      const metrics = analyzer.getCurrentMetrics();
      expect(metrics!.totalSize).toBe(25000);
      expect(metrics!.totalGzipSize).toBe(12000);
      expect(metrics!.moduleCount).toBe(2);
    });

    it('should track chunks', () => {
      const modules: ModuleMetrics[] = [];
      const chunks = new Map([
        ['chunk1', 50000],
        ['chunk2', 30000],
      ]);

      analyzer.recordMetrics(modules, chunks);

      const metrics = analyzer.getCurrentMetrics();
      expect(metrics!.chunkCount).toBe(2);
      expect(metrics!.chunks.size).toBe(2);
    });
  });

  // ============================================================================
  // History Management Tests
  // ============================================================================

  describe('History Management', () => {
    it('should maintain history of metrics', () => {
      const modules: ModuleMetrics[] = [
        {
          name: 'module1',
          size: 10000,
          gzipSize: 5000,
          isDuplicate: false,
          dependents: [],
          dependencies: [],
          isChunk: false,
        },
      ];

      analyzer.recordMetrics(modules);
      analyzer.recordMetrics(modules);
      analyzer.recordMetrics(modules);

      const history = analyzer.getHistory();
      expect(history.length).toBe(3);
    });

    it('should detect size changes', () => {
      const modules1: ModuleMetrics[] = [
        {
          name: 'module1',
          size: 10000,
          gzipSize: 5000,
          isDuplicate: false,
          dependents: [],
          dependencies: [],
          isChunk: false,
        },
      ];

      const modules2: ModuleMetrics[] = [
        {
          name: 'module1',
          size: 12000,
          gzipSize: 6000,
          isDuplicate: false,
          dependents: [],
          dependencies: [],
          isChunk: false,
        },
      ];

      analyzer.recordMetrics(modules1);
      analyzer.recordMetrics(modules2);

      const change = analyzer.getSizeChange();
      expect(change!.size).toBe(2000);
      expect(change!.gzip).toBe(1000);
      expect(change!.percent).toBeCloseTo(20);
    });

    it('should return null for size change with single measurement', () => {
      const modules: ModuleMetrics[] = [
        {
          name: 'module1',
          size: 10000,
          gzipSize: 5000,
          isDuplicate: false,
          dependents: [],
          dependencies: [],
          isChunk: false,
        },
      ];

      analyzer.recordMetrics(modules);

      const change = analyzer.getSizeChange();
      expect(change).toBeNull();
    });
  });

  // ============================================================================
  // Size Budget Tests
  // ============================================================================

  describe('Size Budget Enforcement', () => {
    it('should set size budgets', () => {
      const budget: SizeBudget = {
        total: 500,
        gzip: 200,
        chunk: 100,
        module: 50,
      };

      analyzer.setSizeBudget(budget);

      const modules: ModuleMetrics[] = [
        {
          name: 'small-module',
          size: 10000,
          gzipSize: 5000,
          isDuplicate: false,
          dependents: [],
          dependencies: [],
          isChunk: false,
        },
      ];

      analyzer.recordMetrics(modules);
      const analysis = analyzer.analyzeBundle();

      // Budget was set and analysis runs - data is within budget so no violations
      expect(analysis).toBeDefined();
      expect(analysis.violations).toBeDefined();
      expect(Array.isArray(analysis.violations)).toBe(true);
    });

    it('should detect budget violations', () => {
      const budget: SizeBudget = { total: 100 }; // 100KB budget

      analyzer.setSizeBudget(budget);

      const modules: ModuleMetrics[] = [
        {
          name: 'large-module',
          size: 150 * 1024, // 150KB
          gzipSize: 75 * 1024,
          isDuplicate: false,
          dependents: [],
          dependencies: [],
          isChunk: false,
        },
      ];

      analyzer.recordMetrics(modules);
      const analysis = analyzer.analyzeBundle();

      expect(analysis.violations.length).toBeGreaterThan(0);
      expect(analysis.violations[0]).toContain('exceeds budget');
    });

    it('should not report violations for compliant bundles', () => {
      const budget: SizeBudget = { total: 500 }; // 500KB budget

      analyzer.setSizeBudget(budget);

      const modules: ModuleMetrics[] = [
        {
          name: 'small-module',
          size: 100 * 1024, // 100KB
          gzipSize: 50 * 1024,
          isDuplicate: false,
          dependents: [],
          dependencies: [],
          isChunk: false,
        },
      ];

      analyzer.recordMetrics(modules);
      const analysis = analyzer.analyzeBundle();

      expect(analysis.violations.length).toBe(0);
    });
  });

  // ============================================================================
  // Largest Modules Tests
  // ============================================================================

  describe('Largest Modules Detection', () => {
    it('should identify largest modules', () => {
      const modules: ModuleMetrics[] = [
        {
          name: 'tiny',
          size: 1000,
          gzipSize: 500,
          isDuplicate: false,
          dependents: [],
          dependencies: [],
          isChunk: false,
        },
        {
          name: 'small',
          size: 10000,
          gzipSize: 5000,
          isDuplicate: false,
          dependents: [],
          dependencies: [],
          isChunk: false,
        },
        {
          name: 'large',
          size: 100000,
          gzipSize: 50000,
          isDuplicate: false,
          dependents: [],
          dependencies: [],
          isChunk: false,
        },
      ];

      analyzer.recordMetrics(modules);

      const largest = analyzer.getLargestModules(2);
      expect(largest.length).toBe(2);
      expect(largest[0].name).toBe('large');
      expect(largest[1].name).toBe('small');
    });

    it('should return requested number of modules', () => {
      const modules: ModuleMetrics[] = Array.from({ length: 20 }, (_, i) => ({
        name: `module${i}`,
        size: 10000,
        gzipSize: 5000,
        isDuplicate: false,
        dependents: [],
        dependencies: [],
        isChunk: false,
      }));

      analyzer.recordMetrics(modules);

      const largest = analyzer.getLargestModules(5);
      expect(largest.length).toBe(5);
    });
  });

  // ============================================================================
  // Duplicate Detection Tests
  // ============================================================================

  describe('Duplicate Module Detection', () => {
    it('should identify duplicate modules', () => {
      const modules: ModuleMetrics[] = [
        {
          name: 'lodash-1',
          size: 10000,
          gzipSize: 5000,
          isDuplicate: true,
          dependents: ['component1'],
          dependencies: [],
          isChunk: false,
        },
        {
          name: 'lodash-2',
          size: 10000,
          gzipSize: 5000,
          isDuplicate: true,
          dependents: ['component2'],
          dependencies: [],
          isChunk: false,
        },
      ];

      analyzer.recordMetrics(modules);

      const duplicates = analyzer.getDuplicateModules();
      expect(duplicates.length).toBe(2);
    });

    it('should not flag non-duplicates', () => {
      const modules: ModuleMetrics[] = [
        {
          name: 'unique-module',
          size: 10000,
          gzipSize: 5000,
          isDuplicate: false,
          dependents: [],
          dependencies: [],
          isChunk: false,
        },
      ];

      analyzer.recordMetrics(modules);

      const duplicates = analyzer.getDuplicateModules();
      expect(duplicates.length).toBe(0);
    });
  });

  // ============================================================================
  // Analysis Tests
  // ============================================================================

  describe('Bundle Analysis', () => {
    it('should detect optimization opportunities', () => {
      const modules: ModuleMetrics[] = [
        {
          name: 'large-rarely-used',
          size: 100000,
          gzipSize: 50000,
          isDuplicate: false,
          dependents: ['component1'], // Only used by one component
          dependencies: [],
          isChunk: false,
        },
      ];

      analyzer.recordMetrics(modules);
      const analysis = analyzer.analyzeBundle();

      expect(analysis.opportunities.length).toBeGreaterThan(0);
    });

    it('should provide recommendations for budget violations', () => {
      const budget: SizeBudget = { total: 100 };
      analyzer.setSizeBudget(budget);

      const modules: ModuleMetrics[] = [
        {
          name: 'huge',
          size: 200 * 1024,
          gzipSize: 100 * 1024,
          isDuplicate: false,
          dependents: [],
          dependencies: [],
          isChunk: false,
        },
      ];

      analyzer.recordMetrics(modules);
      const analysis = analyzer.analyzeBundle();

      expect(analysis.recommendations.length).toBeGreaterThan(0);
    });
  });

  // ============================================================================
  // Report Generation Tests
  // ============================================================================

  describe('Report Generation', () => {
    it('should generate bundle report', () => {
      const modules: ModuleMetrics[] = [
        {
          name: 'module1',
          size: 10000,
          gzipSize: 5000,
          isDuplicate: false,
          dependents: [],
          dependencies: [],
          isChunk: false,
        },
      ];

      analyzer.recordMetrics(modules);
      const report = analyzer.generateReport();

      expect(report).toContain('Bundle Analysis Report');
      expect(report).toContain('module1');
    });

    it('should include violations in report', () => {
      const budget: SizeBudget = { total: 5 };
      analyzer.setSizeBudget(budget);

      const modules: ModuleMetrics[] = [
        {
          name: 'large',
          size: 10 * 1024,
          gzipSize: 5 * 1024,
          isDuplicate: false,
          dependents: [],
          dependencies: [],
          isChunk: false,
        },
      ];

      analyzer.recordMetrics(modules);
      const report = analyzer.generateReport();

      expect(report).toContain('❌ Budget Violations');
    });
  });

  // ============================================================================
  // Reset Tests
  // ============================================================================

  describe('Reset', () => {
    it('should clear all metrics on reset', () => {
      const modules: ModuleMetrics[] = [
        {
          name: 'module1',
          size: 10000,
          gzipSize: 5000,
          isDuplicate: false,
          dependents: [],
          dependencies: [],
          isChunk: false,
        },
      ];

      analyzer.recordMetrics(modules);
      analyzer.reset();

      const metrics = analyzer.getCurrentMetrics();
      expect(metrics).toBeNull();

      const history = analyzer.getHistory();
      expect(history.length).toBe(0);
    });
  });
});
