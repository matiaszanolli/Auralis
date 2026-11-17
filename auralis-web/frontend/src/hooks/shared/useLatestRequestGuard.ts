import { useCallback, useRef } from 'react';

/**
 * Returns `begin()`: start a request and get its `isStale()` check (#6275).
 *
 * `isStale()` turns true once any later `begin()` has run, so a request that was overtaken (a fast
 * typist's earlier search, a preset click superseded by the next one) can drop its result instead of
 * overwriting the newer one. This is the request-id counter that the library query, the library
 * pagination and the enhancement commands each hand-rolled; it lives here so a race fix lands once.
 */
export function useLatestRequestGuard(): () => () => boolean {
  const latestRef = useRef(0);
  return useCallback(() => {
    const mine = ++latestRef.current;
    return () => latestRef.current !== mine;
  }, []);
}
