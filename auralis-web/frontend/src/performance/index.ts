/**
 * Performance Optimization Module Index
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Central export point for all performance utilities and tools.
 * Import performance tools from '@/performance' for convenience.
 *
 * Phase C.4b: Performance Optimization
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

// ============================================================================
// Render Profiling
// ============================================================================

export {
  useRenderProfiler,
  renderMetricsStore,
  checkPerformanceWarnings,
} from './useRenderProfiler';

export type { RenderProfilerConfig, PerformanceThreshold } from './useRenderProfiler';

// ============================================================================
// Component Memoization
// ============================================================================

export {
  withMemo,
  withDeepMemo,
  withTrackedMemo,
  shallowEqual,
  deepEqual,
  compareProps,
  useMemoizedList,
  useSelectiveMemo,
} from './withMemo';

export type { MemoConfig, PropsAreEqual } from './withMemo';

// ============================================================================
// Bundle Analysis
// ============================================================================

export {
  bundleAnalyzer,
  extractModuleSizes,
} from './bundleAnalyzer';

export type {
  ModuleMetrics,
  BundleMetrics,
  SizeBudget,
  SizeAnalysis,
} from './bundleAnalyzer';

// ============================================================================
// Lazy Loading & Code Splitting
// ============================================================================

export {
  createLazyComponent,
  dynamicImport,
  modulePreloader,
  createLazyRoutes,
  useRoutePreload,
  ErrorBoundary,
  DefaultLoadingFallback,
  DefaultErrorFallback,
} from './lazyLoader';

export type { LazyComponentConfig, PreloadConfig, RouteConfig } from './lazyLoader';

// ============================================================================
// Redux Advanced Selectors
// ============================================================================

export {
  selectorPerformance,
  createMemoizedSelector,
  playerSelectors,
  queueSelectors,
  cacheSelectors,
  connectionSelectors,
  selectAppSnapshot,
  optimizedSelectors,
} from '../store/selectors/advanced';

export type { SelectorMetrics } from '../store/selectors/advanced';

// ============================================================================
// Performance Monitoring
// ============================================================================

/**
 * Get a comprehensive performance report
 */
export function getPerformanceReport(): string {
  let report = '📊 Comprehensive Performance Report\n';
  report += '====================================\n\n';

  report += '🔄 Redux Selector Performance:\n';
  report += selectorPerformance.report();
  report += '\n\n';

  report += '⚛️  Component Render Performance:\n';
  report += renderMetricsStore.report();
  report += '\n\n';

  report += '📦 Bundle Analysis:\n';
  report += bundleAnalyzer.generateReport();

  return report;
}

/**
 * Reset all performance metrics
 */
export function resetPerformanceMetrics(): void {
  selectorPerformance.reset?.();
  renderMetricsStore.reset();
  bundleAnalyzer.reset();
}

/**
 * Enable performance monitoring
 */
export function enablePerformanceMonitoring(): void {
  // Add performance metrics to window for DevTools access
  if (typeof window !== 'undefined') {
    (window as any).__AURALIS_PERFORMANCE__ = {
      selectors: selectorPerformance,
      rendering: renderMetricsStore,
      bundle: bundleAnalyzer,
    };
  }
}

// ============================================================================
// Exports Summary
// ============================================================================

/**
 * Performance optimization tools available:
 *
 * 1. **Render Profiling**
 *    - useRenderProfiler() - Hook for per-component metrics
 *    - renderMetricsStore - Global render metrics storage
 *    - checkPerformanceWarnings() - Threshold validation
 *
 * 2. **Component Memoization**
 *    - withMemo() - Shallow equality HOC
 *    - withDeepMemo() - Deep equality HOC
 *    - withTrackedMemo() - Memoization with metrics
 *    - compareProps() - Selective prop comparison
 *
 * 3. **Bundle Analysis**
 *    - bundleAnalyzer - Size tracking and budgeting
 *    - Module metrics with recommendations
 *    - Code split opportunity detection
 *
 * 4. **Code Splitting**
 *    - createLazyComponent() - Lazy loading with error recovery
 *    - modulePreloader - Smart preloading
 *    - createLazyRoutes() - Route-based code splitting
 *    - useRoutePreload() - Hover/focus preloading
 *
 * 5. **Redux Optimization**
 *    - Advanced memoized selectors with tracking
 *    - Optimized selectors for all state slices
 *    - Performance metrics integration
 *
 * Usage:
 * ```typescript
 * import {
 *   useRenderProfiler,
 *   withMemo,
 *   bundleAnalyzer,
 *   createLazyComponent,
 *   getPerformanceReport,
 * } from '@/performance';
 * ```
 */
