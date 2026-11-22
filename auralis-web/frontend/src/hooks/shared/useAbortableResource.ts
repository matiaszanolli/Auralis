/**
 * useAbortableResource — load one resource per key into `{data, loading, error}` (#6630).
 *
 * The playlist, album and artist detail hooks each pasted the same scaffold: an AbortController
 * per key so a navigation away cancels the in-flight request and never sets state on a dead
 * component (#3601), the shared transport's ApiError so a 404 and a 500 stay distinguishable
 * (#4643), and the AbortError check for a cancelled request (#5653, #6450). Each hook now keeps
 * only its request and transform, in `fetcher`.
 *
 * `fetcher` and `onLoaded` are read through refs, so inline closures do not re-run the load; only a
 * new `key` does. `loading` starts true: the first render has not loaded anything yet.
 *
 * @module hooks/shared/useAbortableResource
 */

import { useEffect, useState } from 'react';
import type { ApiError } from '@/types/api';
import { ApiErrorHandler } from '@/types/api';
import { isAbortError } from '@/utils/errorGuards';
import { useLatest } from './useLatest';

interface AbortableResourceOptions<T> {
  /** Names the resource in the console error for a failed load. */
  label: string;
  /** Runs with each successful load, in the same batch as `data` (derived state such as a toggle). */
  onLoaded?: (data: T) => void;
}

export interface AbortableResource<T> {
  data: T | null;
  loading: boolean;
  error: ApiError | null;
}

export function useAbortableResource<T>(
  key: unknown,
  fetcher: (signal: AbortSignal) => Promise<T>,
  { label, onLoaded }: AbortableResourceOptions<T>,
): AbortableResource<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const fetcherRef = useLatest(fetcher);
  const onLoadedRef = useLatest(onLoaded);

  useEffect(() => {
    const controller = new AbortController();
    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        const loaded = await fetcherRef.current(controller.signal);
        if (controller.signal.aborted) return;
        setData(loaded);
        onLoadedRef.current?.(loaded);
      } catch (err) {
        if (controller.signal.aborted || isAbortError(err)) return;
        console.error(`Error fetching ${label}:`, err);
        setError(ApiErrorHandler.parse(err));
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    };
    run();
    return () => controller.abort();
  }, [key, label, fetcherRef, onLoadedRef]);

  return { data, loading, error };
}
