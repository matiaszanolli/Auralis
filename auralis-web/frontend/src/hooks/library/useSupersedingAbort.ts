import { useCallback, useEffect, useRef } from 'react';

/**
 * Returns `claim()`: abort the previous request's signal and hand back a fresh
 * one for the new request (#5650).
 *
 * For hooks where a newer request supersedes an older one (search typing, sort
 * change, infinite scroll). Discarding the stale RESPONSE is not enough — the
 * superseded HTTP request would still run to completion against a backend that
 * serves requests serially.
 *
 * The newest request is aborted on unmount too, so a view that is left mid-fetch does not keep
 * a request running whose result nothing will read.
 */
export function useSupersedingAbort(): () => AbortSignal {
  const controllerRef = useRef<AbortController | null>(null);
  useEffect(() => () => controllerRef.current?.abort(), []);
  return useCallback(() => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    return controller.signal;
  }, []);
}
