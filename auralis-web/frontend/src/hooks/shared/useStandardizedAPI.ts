/**
 * Standardized API Hooks — cache, pagination, and batch specializations
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * These hooks are intentional specializations built on `StandardizedAPIClient`
 * (cache-aware responses, pagination envelopes, batch operations) that
 * `useRestAPI` (hooks/api/useRestAPI.ts) does not provide. They are not a
 * competing generic API-client hook (#4300): the generic `useStandardizedAPI()`
 * fetch-on-mount hook that used to live here had exactly one production
 * consumer, which has been migrated to `useRestAPI` — use that for plain
 * REST calls, and reach for the hooks below only when you need their specific
 * cache/pagination/batch behavior.
 *
 * Phase C.1: Frontend Integration
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { useCallback, useEffect, useRef, useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  StandardizedAPIClient,
  CacheAwareAPIClient,
  BatchAPIClient,
  isSuccessResponse,
  PaginatedResponse,
  CacheStats,
  CacheHealth,
  BatchItem,
  BatchItemResult,
  APIClientConfig,
} from '@/services/api/standardizedAPIClient';
import { getAPIClient, initializeAPIClient } from '@/services/api/standardizedAPIClient';
import { API_BASE_URL } from '@/config/api';

// ============================================================================
// Hook State Types
// ============================================================================

export interface APIRequestState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  cacheSource?: 'tier1' | 'tier2' | 'miss';
  processingTimeMs?: number;
}

export interface APICacheStats {
  hits: number;
  misses: number;
  hitRate: number;
  cachedRequests: number;
}


// ============================================================================
// Pagination Hook
// ============================================================================

/**
 * Hook for paginated API requests
 */
export function usePaginatedAPI<T = unknown>(
  endpoint: string,
  options?: {
    initialLimit?: number;
    timeout?: number;
  }
): APIRequestState<T[]> & {
  pagination: {
    limit: number;
    offset: number;
    total: number;
    hasMore: boolean;
    nextPage: () => Promise<void>;
    prevPage: () => Promise<void>;
    goToPage: (pageNumber: number) => Promise<void>;
  };
  refetch: () => Promise<void>;
  reset: () => void;
} {
  const apiClient = useRef<StandardizedAPIClient | null>(null);
  const limit = options?.initialLimit ?? 50;
  const timeout = options?.timeout;

  const [pagination, setPagination] = useState({
    limit,
    offset: 0,
    total: 0,
    hasMore: false
  });

  const [state, setState] = useState<APIRequestState<T[]>>({
    data: [],
    loading: true,
    error: null
  });

  // #4174 (partial regression of #3952, which only covered the initial fetch):
  // track manual page-turn AbortControllers so unmount aborts the in-flight
  // request, and skip post-unmount setState. Mirrors useStandardizedAPI.
  const mountedRef = useRef(true);
  const activeControllers = useRef<Set<AbortController>>(new Set());
  useEffect(() => () => {
    mountedRef.current = false;
    activeControllers.current.forEach((c) => c.abort());
    activeControllers.current.clear();
  }, []);

  useEffect(() => {
    if (!apiClient.current) {
      apiClient.current = getAPIClient();
    }
  }, []);

  const fetchPage = useCallback(async (offset: number = 0, signal?: AbortSignal) => {
    if (!apiClient.current) return;

    setState(prev => ({ ...prev, loading: true }));

    try {
      const response = await apiClient.current.getPaginated<T>(
        endpoint,
        limit,
        offset,
        { timeout, signal }
      );

      if (!mountedRef.current) return;

      if (isSuccessResponse<T[]>(response)) {
        const paginated = response as PaginatedResponse<T>;
        setState({
          data: paginated.data,
          loading: false,
          error: null,
          cacheSource: paginated.cache_source,
          processingTimeMs: paginated.processing_time_ms
        });

        setPagination({
          limit: paginated.pagination.limit,
          offset: paginated.pagination.offset,
          total: paginated.pagination.total,
          hasMore: paginated.pagination.has_more
        });
      } else {
        setState({
          data: [],
          loading: false,
          error: response.message
        });
      }
    } catch (error) {
      // Don't surface abort errors as UI errors (#3952).
      if (error instanceof DOMException && error.name === 'AbortError') return;
      if (!mountedRef.current) return;
      setState({
        data: [],
        loading: false,
        error: error instanceof Error ? error.message : 'Failed to fetch page'
      });
    }
  }, [endpoint, limit, timeout]);

  // Auto-fetch the first page on mount, aborting the in-flight request on
  // unmount so state setters don't fire on an unmounted component (#3952).
  useEffect(() => {
    const controller = new AbortController();
    fetchPage(0, controller.signal);
    return () => controller.abort();
  }, [fetchPage]);

  const reset = useCallback(() => {
    setState({ data: [], loading: false, error: null });
    setPagination({ limit, offset: 0, total: 0, hasMore: false });
  }, [limit]);

  // Run a manual page request under a tracked AbortController so unmount cancels
  // it and fetchPage's mountedRef guards skip post-unmount setState (#4174).
  const runTracked = useCallback(async (offset: number) => {
    const controller = new AbortController();
    activeControllers.current.add(controller);
    try {
      await fetchPage(offset, controller.signal);
    } finally {
      activeControllers.current.delete(controller);
    }
  }, [fetchPage]);

  const nextPage = useCallback(async () => {
    if (pagination.hasMore) {
      await runTracked(pagination.offset + limit);
    }
  }, [pagination.hasMore, pagination.offset, limit, runTracked]);

  const prevPage = useCallback(async () => {
    if (pagination.offset > 0) {
      await runTracked(Math.max(0, pagination.offset - limit));
    }
  }, [pagination.offset, limit, runTracked]);

  const goToPage = useCallback(async (pageNumber: number) => {
    const offset = (pageNumber - 1) * limit;
    await runTracked(offset);
  }, [limit, runTracked]);

  const refetch = useCallback(
    () => runTracked(pagination.offset),
    [runTracked, pagination.offset]
  );

  return {
    ...state,
    pagination: {
      ...pagination,
      nextPage,
      prevPage,
      goToPage,
    },
    refetch,
    reset,
  };
}

// ============================================================================
// Cache Hooks
// ============================================================================

// Shared client instance for cache queries (avoids recreating per hook call)
let _cacheClient: CacheAwareAPIClient | null = null;
function getCacheClient(): CacheAwareAPIClient {
  if (!_cacheClient) {
    _cacheClient = new CacheAwareAPIClient(getAPIClient());
  }
  return _cacheClient;
}

/**
 * Hook for monitoring cache statistics (#2806: React Query for dedup)
 */
export function useCacheStats(): APIRequestState<CacheStats> & {
  refetch: () => Promise<void>;
} {
  const query = useQuery<CacheStats | null>({
    queryKey: ['cache', 'stats'],
    queryFn: () => getCacheClient().getCacheStats(),
    refetchInterval: 5000,
  });

  const refetchRef = useRef(query.refetch);
  refetchRef.current = query.refetch;
  const stableRefetch = useCallback(async () => { await refetchRef.current(); }, []);

  return useMemo(() => ({
    data: query.data ?? null,
    loading: query.isLoading,
    error: query.error ? query.error.message : null,
    refetch: stableRefetch,
  }), [query.data, query.isLoading, query.error, stableRefetch]);
}

/**
 * Hook for monitoring cache health (#2806: React Query for dedup)
 */
export function useCacheHealth(refreshInterval: number = 10000): APIRequestState<CacheHealth> & {
  refetch: () => Promise<void>;
  isHealthy: boolean;
  healthStatus: 'healthy' | 'critical';
} {
  const query = useQuery<CacheHealth | null>({
    queryKey: ['cache', 'health'],
    queryFn: () => getCacheClient().getCacheHealth(),
    refetchInterval: refreshInterval,
  });

  const refetchRef = useRef(query.refetch);
  refetchRef.current = query.refetch;
  const stableRefetch = useCallback(async () => { await refetchRef.current(); }, []);

  return useMemo(() => ({
    data: query.data ?? null,
    loading: query.isLoading,
    error: query.error ? query.error.message : null,
    refetch: stableRefetch,
    isHealthy: query.data?.healthy ?? false,
    healthStatus: query.data?.healthy ? 'healthy' as const : 'critical' as const,
  }), [query.data, query.isLoading, query.error, stableRefetch]);
}

// ============================================================================
// Batch Operations Hook
// ============================================================================

/**
 * Hook for batch operations
 */
export function useBatchOperations(): {
  executeBatch: (items: BatchItem[], atomic?: boolean) => Promise<BatchItemResult[] | null>;
  favoriteTracks: (trackIds: string[]) => Promise<boolean>;
  removeTracks: (trackIds: string[]) => Promise<boolean>;
  loading: boolean;
  error: string | null;
} {
  const apiClient = useRef<BatchAPIClient | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!apiClient.current) {
      const baseClient = getAPIClient();
      apiClient.current = new BatchAPIClient(baseClient);
    }
  }, []);

  // #3589: wrap each operation in useCallback so consumers can pass them to
  // useEffect deps / memoized children without forcing re-runs every render.
  // apiClient is a ref so no deps are needed.
  const executeBatch = useCallback(
    async (items: BatchItem[], atomic: boolean = false) => {
      if (!apiClient.current) return null;
      setLoading(true);
      setError(null);
      try {
        return await apiClient.current.executeBatch(items, atomic);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Batch operation failed';
        setError(message);
        return null;
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const favoriteTracks = useCallback(async (trackIds: string[]) => {
    if (!apiClient.current) return false;
    setLoading(true);
    setError(null);
    try {
      return await apiClient.current.favoriteTracks(trackIds);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to favorite tracks';
      setError(message);
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  const removeTracks = useCallback(async (trackIds: string[]) => {
    if (!apiClient.current) return false;
    setLoading(true);
    setError(null);
    try {
      return await apiClient.current.removeTracks(trackIds);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to remove tracks';
      setError(message);
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  return useMemo(
    () => ({ executeBatch, favoriteTracks, removeTracks, loading, error }),
    [executeBatch, favoriteTracks, removeTracks, loading, error]
  );
}

// ============================================================================
// API Client Initialization Hook
// ============================================================================

/**
 * Hook to initialize API client at app startup
 */
export function useInitializeAPI(config?: Partial<APIClientConfig>): void {
  useEffect(() => {
    const baseURL = config?.baseURL ?? import.meta.env.VITE_API_URL ?? API_BASE_URL;

    initializeAPIClient({
      baseURL,
      timeout: config?.timeout ?? 30000,
      retryAttempts: config?.retryAttempts ?? 3,
      cacheResponses: config?.cacheResponses ?? true,
      cacheTTL: config?.cacheTTL ?? 60000,
    });

    console.log('[API] Hooks initialized with baseURL:', baseURL);
    // #3627: include all config primitives consumed inside the effect so a
    // caller passing a dynamic config gets the API client re-initialised.
  }, [
    config?.baseURL,
    config?.timeout,
    config?.retryAttempts,
    config?.cacheResponses,
    config?.cacheTTL,
  ]);
}
