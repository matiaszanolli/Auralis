/**
 * React.lazy that survives a failed chunk load (#6035).
 *
 * `lazy()` caches its first rejection forever: after a transient network error loading a route
 * chunk, an error boundary's "Try again" re-rendered the same rejected lazy component and crashed
 * identically, so the dialog or view could not be recovered without reloading the app. Here a
 * failed import is retried a couple of times with a short back-off (a flaky read of a local
 * chunk usually clears), and when it still fails the next render gets a FRESH lazy, so the
 * boundary's retry performs a new import instead of replaying the stored failure.
 *
 * @module utils/lazyWithRetry
 */

import { lazy, useContext, type ComponentType, type LazyExoticComponent } from 'react';
import { ErrorBoundaryResetContext } from '@/components/core/ErrorBoundary';

const RETRY_DELAYS_MS = [250, 1000];

async function importWithRetry<T>(importer: () => Promise<T>, delays: readonly number[]): Promise<T> {
  for (const delay of delays) {
    try {
      return await importer();
    } catch {
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }
  return importer();
}

export function lazyWithRetry<P extends object>(
  importer: () => Promise<{ default: ComponentType<P> }>,
  delays: readonly number[] = RETRY_DELAYS_MS,
): ComponentType<P> {
  // The boundary reset count at the last render, and at which a load last failed (null: none).
  let lastResetSeen = 0;
  let failedAtReset: number | null = null;

  const make = (): LazyExoticComponent<ComponentType<P>> =>
    lazy(() =>
      importWithRetry(importer, delays).catch((error: unknown) => {
        failedAtReset = lastResetSeen;
        throw error;
      }),
    );
  let Current = make();

  const LazyWithRetry = (props: P) => {
    const resetCount = useContext(ErrorBoundaryResetContext);
    // A rejected lazy replays its failure forever. The boundary resetting after the failure is
    // the retry: import afresh. Rendering again for any other reason (React re-attempting the
    // suspended tree) keeps the stored failure, so a dead chunk reaches the boundary instead of
    // being re-fetched in a loop.
    if (failedAtReset !== null && resetCount !== failedAtReset) {
      failedAtReset = null;
      Current = make();
    }
    lastResetSeen = resetCount;
    const Component = Current as unknown as ComponentType<P>;
    return <Component {...props} />;
  };
  LazyWithRetry.displayName = 'LazyWithRetry';
  return LazyWithRetry;
}
