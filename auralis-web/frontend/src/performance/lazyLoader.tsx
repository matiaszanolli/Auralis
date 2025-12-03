/**
 * Lazy Loading and Code Splitting Utilities
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tools for implementing lazy loading and code splitting in React applications.
 * Helps reduce initial bundle size by splitting code into smaller chunks.
 *
 * Features:
 * - React.lazy() wrapper with error boundaries
 * - Async component loading with loading/error states
 * - Suspense boundaries with fallback UI
 * - Dynamic imports with retry logic
 * - Preload hints for route-based code splitting
 * - Module preloading utilities
 *
 * Phase C.4b: Performance Optimization
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import React, { lazy, Suspense, ReactNode, ComponentType, ReactElement } from 'react';

// ============================================================================
// Types
// ============================================================================

interface LazyComponentConfig {
  fallback?: ReactNode;
  onError?: (error: Error) => void;
  retries?: number;
  retryDelay?: number;
}

interface PreloadConfig {
  timeout?: number;
  onSuccess?: () => void;
  onError?: (error: Error) => void;
}

// ============================================================================
// Error Boundary
// ============================================================================

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    this.props.onError?.(error, errorInfo);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        this.props.fallback || (
          <div style={{ padding: '20px', textAlign: 'center', color: '#d32f2f' }}>
            <h2>Failed to load component</h2>
            <p>{this.state.error?.message}</p>
          </div>
        )
      );
    }

    return this.props.children;
  }
}

// ============================================================================
// Loading Fallback Components
// ============================================================================

export const DefaultLoadingFallback = () => (
  <div
    style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px',
      minHeight: '100px',
    }}
  >
    <div style={{ textAlign: 'center', color: '#666' }}>
      <p>Loading...</p>
    </div>
  </div>
);

export const DefaultErrorFallback = ({ error }: { error?: Error }) => (
  <div
    style={{
      padding: '20px',
      textAlign: 'center',
      color: '#d32f2f',
      border: '1px solid #d32f2f',
      borderRadius: '4px',
    }}
  >
    <h3>Failed to load component</h3>
    <p>{error?.message || 'An error occurred while loading this component'}</p>
  </div>
);

// ============================================================================
// Lazy Loading HOC
// ============================================================================

/**
 * Create a lazy-loaded component with error boundary and suspense
 */
export function createLazyComponent<T extends ComponentType<any>>(
  importFn: () => Promise<{ default: T }>,
  config: LazyComponentConfig = {}
): React.MemoExoticComponent<(props: React.ComponentProps<T>) => ReactElement> {
  let LazyComponent: React.LazyExoticComponent<T>;
  let retryCount = 0;
  const maxRetries = config.retries ?? 3;

  // Wrapper for retry logic
  const loadComponent = async (): Promise<{ default: T }> => {
    try {
      return await importFn();
    } catch (error) {
      if (retryCount < maxRetries) {
        retryCount++;
        const delay = config.retryDelay ?? 1000;
        await new Promise((resolve) => setTimeout(resolve, delay * retryCount));
        return loadComponent();
      }
      throw error;
    }
  };

  LazyComponent = lazy(loadComponent);

  const Component = (props: React.ComponentProps<T>): ReactElement => (
    <ErrorBoundary
      fallback={<DefaultErrorFallback />}
      onError={(error) => config.onError?.(error)}
    >
      <Suspense fallback={config.fallback || <DefaultLoadingFallback />}>
        <LazyComponent {...props} />
      </Suspense>
    </ErrorBoundary>
  );

  Component.displayName = 'LazyComponent';

  return React.memo(Component);
}

// ============================================================================
// Dynamic Import with Retry
// ============================================================================

/**
 * Dynamically import a module with retry logic
 */
export async function dynamicImport<T>(
  importFn: () => Promise<T>,
  config: { retries?: number; retryDelay?: number } = {}
): Promise<T> {
  const maxRetries = config.retries ?? 3;
  let lastError: Error | null = null;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await importFn();
    } catch (error) {
      lastError = error as Error;
      if (attempt < maxRetries - 1) {
        const delay = config.retryDelay ?? 1000;
        await new Promise((resolve) => setTimeout(resolve, delay * (attempt + 1)));
      }
    }
  }

  throw lastError || new Error('Failed to import module after retries');
}

// ============================================================================
// Module Preloading
// ============================================================================

class ModulePreloader {
  private preloadedModules: Set<string> = new Set();
  private preloadQueue: Map<string, Promise<any>> = new Map();

  /**
   * Preload a module
   */
  async preload(
    id: string,
    importFn: () => Promise<any>,
    config: PreloadConfig = {}
  ): Promise<void> {
    if (this.preloadedModules.has(id)) {
      return;
    }

    if (this.preloadQueue.has(id)) {
      return this.preloadQueue.get(id);
    }

    const timeout = config.timeout || 10000;
    const preloadPromise = Promise.race([
      dynamicImport(importFn, { retries: 3 }),
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error('Preload timeout')), timeout)
      ),
    ])
      .then(() => {
        this.preloadedModules.add(id);
        config.onSuccess?.();
      })
      .catch((error) => {
        config.onError?.(error as Error);
      })
      .finally(() => {
        this.preloadQueue.delete(id);
      });

    this.preloadQueue.set(id, preloadPromise);
    await preloadPromise;
  }

  /**
   * Preload multiple modules in parallel
   */
  async preloadMany(
    modules: Array<{ id: string; importFn: () => Promise<any> }>,
    config: PreloadConfig = {}
  ): Promise<void> {
    await Promise.all(
      modules.map((m) => this.preload(m.id, m.importFn, config))
    );
  }

  /**
   * Preload a route's components
   */
  async preloadRoute(
    route: string,
    components: Array<{ id: string; importFn: () => Promise<any> }>,
    config: PreloadConfig = {}
  ): Promise<void> {
    console.debug(`Preloading components for route: ${route}`);
    await this.preloadMany(components, config);
  }

  /**
   * Get preload status
   */
  getStatus(): {
    preloaded: string[];
    preloading: string[];
  } {
    return {
      preloaded: Array.from(this.preloadedModules),
      preloading: Array.from(this.preloadQueue.keys()),
    };
  }

  /**
   * Clear cache
   */
  clear(): void {
    this.preloadedModules.clear();
    this.preloadQueue.clear();
  }
}

export const modulePreloader = new ModulePreloader();

// ============================================================================
// Route-based Code Splitting
// ============================================================================

interface RouteConfig {
  path: string;
  component: () => Promise<{ default: ComponentType<any> }>;
  preload?: boolean;
}

/**
 * Create lazy-loaded routes
 */
export function createLazyRoutes(
  routes: RouteConfig[]
): Array<{ path: string; component: React.LazyExoticComponent<any>; preload?: boolean }> {
  return routes.map((route) => ({
    ...route,
    component: lazy(route.component),
  }));
}

/**
 * Preload route on hover/focus
 */
export function useRoutePreload(
  importFn: () => Promise<{ default: any }>,
  config: PreloadConfig = {}
) {
  return {
    onMouseEnter: () => {
      dynamicImport(importFn).catch((error) => {
        config.onError?.(error as Error);
      });
    },
    onFocus: () => {
      dynamicImport(importFn).catch((error) => {
        config.onError?.(error as Error);
      });
    },
  };
}

export type { LazyComponentConfig, PreloadConfig, RouteConfig };
