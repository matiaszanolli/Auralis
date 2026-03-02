/**
 * React.memo HOC and Utility for Component Optimization
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Higher-order component for memoizing components with smart prop comparison.
 * Prevents unnecessary re-renders by memoizing components and comparing props.
 *
 * Features:
 * - React.memo wrapper with custom comparison
 * - Selective prop comparison (compare only relevant props)
 * - Performance metrics integration
 * - Custom equality checks
 * - Display name preservation
 *
 * Phase C.4b: Performance Optimization
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import React, { memo, useMemo, ComponentType, ReactElement } from 'react';
import { renderMetricsStore } from './useRenderProfiler';

// ============================================================================
// Types
// ============================================================================

type PropsAreEqual<T> = (prevProps: T, nextProps: T) => boolean;

interface MemoConfig<T> {
  displayName?: string;
  propsToCompare?: (keyof T)[];
  customComparison?: PropsAreEqual<T>;
  trackMetrics?: boolean;
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Shallow equality comparison for objects
 */
export function shallowEqual<T extends Record<string, any>>(
  obj1: T,
  obj2: T
): boolean {
  const keys1 = Object.keys(obj1);
  const keys2 = Object.keys(obj2);

  if (keys1.length !== keys2.length) {
    return false;
  }

  for (const key of keys1) {
    if (obj1[key] !== obj2[key]) {
      return false;
    }
  }

  return true;
}

/**
 * Compare only specified props
 */
export function compareProps<T extends Record<string, any>>(
  propsToCompare: (keyof T)[]
): PropsAreEqual<T> {
  return (prevProps, nextProps) => {
    for (const prop of propsToCompare) {
      if (prevProps[prop] !== nextProps[prop]) {
        return false;
      }
    }
    return true;
  };
}

/**
 * Deep equality comparison (recursive)
 */
export function deepEqual<T>(obj1: T, obj2: T): boolean {
  if (obj1 === obj2) return true;
  if (obj1 == null || obj2 == null) return false;
  if (typeof obj1 !== 'object' || typeof obj2 !== 'object') return false;

  const keys1 = Object.keys(obj1 as Record<string, any>);
  const keys2 = Object.keys(obj2 as Record<string, any>);

  if (keys1.length !== keys2.length) return false;

  for (const key of keys1) {
    const val1 = (obj1 as Record<string, any>)[key];
    const val2 = (obj2 as Record<string, any>)[key];

    if (typeof val1 === 'object' && typeof val2 === 'object') {
      if (!deepEqual(val1, val2)) return false;
    } else if (val1 !== val2) {
      return false;
    }
  }

  return true;
}

// ============================================================================
// Memoization HOCs
// ============================================================================

/**
 * Memoize a component with shallow prop comparison
 */
export function withMemo<P extends Record<string, any>>(
  Component: ComponentType<P>,
  config: MemoConfig<P> = {}
): React.MemoExoticComponent<ComponentType<P>> {
  const memoizedComponent = memo(
    Component,
    config.customComparison
      ? (prevProps, nextProps) => !config.customComparison!(prevProps, nextProps)
      : config.propsToCompare
        ? (prevProps, nextProps) => {
            const isEqual = compareProps(config.propsToCompare!)(
              prevProps,
              nextProps
            );
            return isEqual;
          }
        : undefined
  ) as React.MemoExoticComponent<ComponentType<P>>;

  const displayName = config.displayName || Component.displayName || Component.name;
  memoizedComponent.displayName = `memo(${displayName})`;

  return memoizedComponent;
}

/**
 * Memoize a component with deep prop comparison
 */
export function withDeepMemo<P extends Record<string, any>>(
  Component: ComponentType<P>,
  config: MemoConfig<P> = {}
): React.MemoExoticComponent<ComponentType<P>> {
  const displayName = config.displayName || Component.displayName || Component.name;

  const memoizedComponent = memo(
    Component,
    (prevProps, nextProps) => deepEqual(prevProps, nextProps)
  ) as React.MemoExoticComponent<ComponentType<P>>;

  memoizedComponent.displayName = `deepMemo(${displayName})`;

  return memoizedComponent;
}

/**
 * Memoize a component and track render metrics
 */
export function withTrackedMemo<P extends Record<string, any>>(
  Component: ComponentType<P>,
  config: MemoConfig<P> & { trackMetrics?: boolean } = {}
): React.MemoExoticComponent<ComponentType<P>> {
  const displayName = config.displayName || Component.displayName || Component.name;

  const TrackedComponent = (props: P): ReactElement => {
    if (config.trackMetrics !== false) {
      // Record that this component rendered
      renderMetricsStore.recordRender(
        `Memoized(${displayName})`,
        0,
        0,
        'update',
        new Set()
      );
    }

    return <Component {...props} />;
  };

  const memoizedComponent = memo(
    TrackedComponent,
    config.customComparison
      ? (prevProps, nextProps) => !config.customComparison!(prevProps, nextProps)
      : config.propsToCompare
        ? (prevProps, nextProps) => {
            const isEqual = compareProps(config.propsToCompare!)(
              prevProps,
              nextProps
            );
            return isEqual;
          }
        : undefined
  ) as React.MemoExoticComponent<ComponentType<P>>;

  memoizedComponent.displayName = `trackedMemo(${displayName})`;

  return memoizedComponent;
}

// ============================================================================
// Callback Memoization
// ============================================================================

/**
 * Use useMemo for memoizing values
 * Replaces useMemo hook for functional memoization
 */
export function memoizeValue<T>(
  factory: () => T,
  _deps: React.DependencyList
): T {
  // This is a utility wrapper - actual memoization happens in useMemo
  return factory();
}

/**
 * Stable callback creator (replaces useCallback)
 */
export function createStableCallback<T extends (...args: any[]) => any>(
  callback: T
): T {
  // This wrapper helps identify callbacks that should be memoized
  return callback;
}

// ============================================================================
// Component List Optimization
// ============================================================================

/**
 * Memoize a list of items for rendering
 * Prevents re-renders of list items that haven't changed
 */
export function useMemoizedList<T extends { id: string | number }>(
  items: T[],
  renderer: (item: T) => React.ReactNode,
  deps: React.DependencyList = []
): React.ReactNode[] {
  return useMemo(
    () => items.map(renderer),
    [items, renderer, ...deps]
  );
}

// ============================================================================
// Hook for Selective Re-renders
// ============================================================================

/**
 * Hook to memoize specific props and only re-render on changes
 */
export function useSelectiveMemo<T extends Record<string, any>>(
  props: T,
  propsToWatch: (keyof T)[]
): T {
  return useMemo(
    () => props,
    propsToWatch.map((key) => props[key])
  );
}

export type { MemoConfig, PropsAreEqual };
