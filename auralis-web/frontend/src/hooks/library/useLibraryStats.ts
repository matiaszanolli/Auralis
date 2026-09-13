import { useState, useCallback, useEffect, useRef } from 'react';
import { type LibraryStats } from '@/types/domain';
import { get } from '@/utils/apiRequest';
import { isAbortError } from '@/utils/errorGuards';

export type { LibraryStats };

export interface UseLibraryStatsOptions {
  includeStats: boolean;
}

export interface UseLibraryStatsReturn {
  stats: LibraryStats | null;
  statsLoading: boolean;
  statsError: string | null;
  refetchStats: () => Promise<void>;
  statsAbortRef: React.MutableRefObject<AbortController | null>;
}

export const useLibraryStats = ({ includeStats }: UseLibraryStatsOptions): UseLibraryStatsReturn => {
  const [stats, setStats] = useState<LibraryStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(includeStats);
  const [statsError, setStatsError] = useState<string | null>(null);
  const statsAbortRef = useRef<AbortController | null>(null);

  // Abort in-flight stats request on unmount.
  useEffect(() => {
    return () => { statsAbortRef.current?.abort(); };
  }, []);

  const refetchStats = useCallback(async () => {
    if (!includeStats) return;

    statsAbortRef.current?.abort();
    const controller = new AbortController();
    statsAbortRef.current = controller;

    setStatsLoading(true);
    setStatsError(null);
    try {
      // #5019: routed through the shared transport, which composes
      // DEFAULT_TIMEOUT_MS with the unmount signal below. The raw fetch() this
      // replaces had no upper bound, so a hung backend left statsLoading stuck
      // true for as long as the view stayed mounted.
      const data = await get<LibraryStats>('/api/library/stats', { signal: controller.signal });
      if (controller.signal.aborted) return;
      setStats(data);
    } catch (err) {
      // get() wraps even a caller-triggered abort into an APIRequestError
      // rather than preserving AbortError's `.name`, so the signal — not the
      // error shape — is what authoritatively identifies a cancellation.
      if (controller.signal.aborted || isAbortError(err)) return;
      const message = err instanceof Error ? err.message : 'Failed to fetch stats';
      console.error('Error fetching library stats:', err);
      setStatsError(message);
    } finally {
      if (!controller.signal.aborted) {
        setStatsLoading(false);
      }
    }
  }, [includeStats]);

  return { stats, statsLoading, statsError, refetchStats, statsAbortRef };
};
