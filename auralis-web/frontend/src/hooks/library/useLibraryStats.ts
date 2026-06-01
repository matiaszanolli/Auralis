import { useState, useCallback, useEffect, useRef } from 'react';
import { type LibraryStats } from '@/types/domain';

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
      const response = await fetch('/api/library/stats', { signal: controller.signal });
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const data: LibraryStats = await response.json();
      setStats(data);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
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
