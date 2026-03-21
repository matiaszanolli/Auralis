/**
 * useStandardizedAPI Hook
 * ~~~~~~~~~~~~~~~~~~~~~~~
 *
 * React hook for accessing standardized API client with automatic error handling,
 * loading states, and cache management.
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
  SuccessResponse,
  ErrorResponse,
  isSuccessResponse,
  PaginatedResponse,
  CacheStats,
  CacheHealth,
  BatchItem,
  BatchItemResult,
  APIClientConfig,
  RequestOptions
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
// Main API Hook
// ============================================================================

/**
 * Hook for making standardized API requests
 */
export function useStandardizedAPI<T = unknown>(
  endpoint: string,
  options?: {
    method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
    body?: Record<string, any>;
    autoFetch?: boolean;
    timeout?: number;
    cache?: boolean;
    deps?: any[];
  }
): APIRequestState<T> & {
  refetch: () => Promise<void>;
  reset: () => void;
} {
  const apiClient = useRef<StandardizedAPIClient | null>(null);
  const [state, setState] = useState<APIRequestState<T>>({
    data: null,
    loading: true,
    error: null
  });

  // Destructure primitives so inline option objects don't cause dependency churn
  const method = options?.method ?? 'GET';
  const timeout = options?.timeout;
  const cache = options?.cache ?? true;
  const autoFetch = options?.autoFetch !== false;

  // Keep body in a ref — updated every render so fetch always sees the latest
  // value, but changes to body don't recreate the callback
  const bodyRef = useRef(options?.body);
  bodyRef.current = options?.body;

  // Initialize API client
  useEffect(() => {
    if (!apiClient.current) {
      apiClient.current = getAPIClient();
    }
  }, []);

  // Fetch data
  const fetch = useCallback(async () => {
    if (!apiClient.current) return;

    setState(prev => ({ ...prev, loading: true, error: null }));

    try {
      const requestOptions: RequestOptions = {
        method,
        timeout,
        cache
      };

      let response: SuccessResponse<T> | ErrorResponse;

      if (method === 'POST') {
        response = await apiClient.current.post<T>(endpoint, bodyRef.current, requestOptions);
      } else if (method === 'PUT') {
        response = await apiClient.current.put<T>(endpoint, bodyRef.current, requestOptions);
      } else if (method === 'DELETE') {
        response = await apiClient.current.delete<T>(endpoint, requestOptions);
      } else {
        response = await apiClient.current.get<T>(endpoint, requestOptions);
      }

      if (isSuccessResponse<T>(response)) {
        setState({
          data: response.data,
          loading: false,
          error: null,
          cacheSource: response.cache_source,
          processingTimeMs: response.processing_time_ms
        });
      } else {
        setState({
          data: null,
          loading: false,
          error: response.message || 'Request failed',
          cacheSource: undefined,
          processingTimeMs: undefined
        });
      }
    } catch (error) {
      setState({
        data: null,
        loading: false,
        error: error instanceof Error ? error.message : 'Unknown error occurred',
        cacheSource: undefined,
        processingTimeMs: undefined
      });
    }
  }, [endpoint, method, timeout, cache]); // primitives only — no object references

  // Auto-fetch on mount or when dependencies change.
  // Spread options.deps so individual values are compared, not the array reference.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (autoFetch) {
      fetch();
    }
  }, [fetch, ...(options?.deps ?? [])]);

  return {
    ...state,
    refetch: fetch,
    reset: () => setState({ data: null, loading: false, error: null })
  };
}

// ============================================================================
// Pagination Hook
// ============================================================================

/**
 * Hook for paginated API requests
 */
export function usePaginatedAPI<T = any>(
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
} {
  const apiClient = useRef<StandardizedAPIClient | null>(null);
  const limit = options?.initialLimit ?? 50;

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

  useEffect(() => {
    if (!apiClient.current) {
      apiClient.current = getAPIClient();
    }
  }, []);

  const fetchPage = useCallback(async (offset: number = 0) => {
    if (!apiClient.current) return;

    setState(prev => ({ ...prev, loading: true }));

    try {
      const response = await apiClient.current.getPaginated<T>(
        endpoint,
        limit,
        offset,
        { timeout: options?.timeout }
      );

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
      setState({
        data: [],
        loading: false,
        error: error instanceof Error ? error.message : 'Failed to fetch page'
      });
    }
  }, [endpoint, limit, options?.timeout]);

  useEffect(() => {
    fetchPage(0);
  }, [fetchPage]);

  return {
    ...state,
    pagination: {
      ...pagination,
      nextPage: async () => {
        if (pagination.hasMore) {
          await fetchPage(pagination.offset + limit);
        }
      },
      prevPage: async () => {
        if (pagination.offset > 0) {
          await fetchPage(Math.max(0, pagination.offset - limit));
        }
      },
      goToPage: async (pageNumber: number) => {
        const offset = (pageNumber - 1) * limit;
        await fetchPage(offset);
      }
    },
    refetch: () => fetchPage(pagination.offset)
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

  return useMemo(() => ({
    data: query.data ?? null,
    loading: query.isLoading,
    error: query.error ? query.error.message : null,
    refetch: async () => { await query.refetch(); },
  }), [query.data, query.isLoading, query.error, query.refetch]);
}

/**
 * Hook for monitoring cache health (#2806: React Query for dedup)
 */
export function useCacheHealth(): APIRequestState<CacheHealth> & {
  refetch: () => Promise<void>;
  isHealthy: boolean;
  healthStatus: 'healthy' | 'warning' | 'critical';
} {
  const query = useQuery<CacheHealth | null>({
    queryKey: ['cache', 'health'],
    queryFn: () => getCacheClient().getCacheHealth(),
    refetchInterval: 10000,
  });

  return useMemo(() => ({
    data: query.data ?? null,
    loading: query.isLoading,
    error: query.error ? query.error.message : null,
    refetch: async () => { await query.refetch(); },
    isHealthy: query.data?.healthy ?? false,
    healthStatus: query.data?.healthy ? 'healthy' as const : 'critical' as const,
  }), [query.data, query.isLoading, query.error, query.refetch]);
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

  return {
    executeBatch: async (items: BatchItem[], atomic: boolean = false) => {
      if (!apiClient.current) return null;

      setLoading(true);
      setError(null);

      try {
        const results = await apiClient.current.executeBatch(items, atomic);
        return results;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Batch operation failed';
        setError(message);
        return null;
      } finally {
        setLoading(false);
      }
    },

    favoriteTracks: async (trackIds: string[]) => {
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
    },

    removeTracks: async (trackIds: string[]) => {
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
    },

    loading,
    error
  };
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
      cacheTTL: config?.cacheTTL ?? 60000
    });

    console.log('[API] Hooks initialized with baseURL:', baseURL);
  }, [config?.baseURL, config?.timeout]);
}
