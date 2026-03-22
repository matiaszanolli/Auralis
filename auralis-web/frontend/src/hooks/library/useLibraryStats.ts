import { useState, useEffect, useCallback, useRef } from 'react';
import type { LibraryStats } from '@/types/domain';

interface UseLibraryStatsReturn {
  stats: LibraryStats | null;
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

export const useLibraryStats = (): UseLibraryStatsReturn => {
  const [stats, setStats] = useState<LibraryStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const fetchStats = useCallback(async () => {
    // Abort any in-flight request before starting a new one
    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      setIsLoading(true);
      setError(null);

      const response = await fetch('/api/library/stats', { signal: controller.signal });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setStats(data);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch stats';
      setError(errorMessage);
      console.error('Error fetching library stats:', err);
    } finally {
      if (!controller.signal.aborted) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    fetchStats();
    return () => { abortControllerRef.current?.abort(); };
  }, [fetchStats]);

  return { stats, isLoading, error, refetch: fetchStats };
};