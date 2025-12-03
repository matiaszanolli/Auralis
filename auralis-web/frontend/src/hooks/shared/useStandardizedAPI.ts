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

import { useCallback, useEffect, useRef, useState } from 'react';
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

export interface CacheHealth {
  healthy: boolean;
  tier1Size: number;
  tier2Size: number;
  totalSize: number;
  tier1HitRate: number;
  overallHitRate: number;
}

// ============================================================================
// Main API Hook
// ============================================================================

/**
 * Hook for making standardized API requests
 */
export function useStandardizedAPI<T = any>(
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
        method: options?.method ?? 'GET',
        timeout: options?.timeout,
        cache: options?.cache ?? true
      };

      let response: SuccessResponse<T> | ErrorResponse;

      if (options?.method === 'POST') {
        response = await apiClient.current.post<T>(endpoint, options.body, requestOptions);
      } else if (options?.method === 'PUT') {
        response = await apiClient.current.put<T>(endpoint, options.body, requestOptions);
      } else if (options?.method === 'DELETE') {
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
  }, [endpoint, options]);

  // Auto-fetch on mount or when dependencies change
  useEffect(() => {
    if (options?.autoFetch !== false) {
      fetch();
    }
  }, [fetch, options?.deps]);

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

/**
 * Hook for monitoring cache statistics
 */
export function useCacheStats(): APIRequestState<CacheStats> & {
  refetch: () => Promise<void>;
} {
  const apiClient = useRef<CacheAwareAPIClient | null>(null);
  const [state, setState] = useState<APIRequestState<CacheStats>>({
    data: null,
    loading: true,
    error: null
  });

  useEffect(() => {
    if (!apiClient.current) {
      const baseClient = getAPIClient();
      apiClient.current = new CacheAwareAPIClient(baseClient);
    }
  }, []);

  const fetchStats = useCallback(async () => {
    if (!apiClient.current) return;

    setState(prev => ({ ...prev, loading: true }));

    try {
      const data = await apiClient.current.getCacheStats();
      if (data) {
        setState({
          data,
          loading: false,
          error: null
        });
      } else {
        setState({
          data: null,
          loading: false,
          error: 'Failed to fetch cache stats'
        });
      }
    } catch (error) {
      setState({
        data: null,
        loading: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  }, []);

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval);
  }, [fetchStats]);

  return {
    ...state,
    refetch: fetchStats
  };
}

/**
 * Hook for monitoring cache health
 */
export function useCacheHealth(): APIRequestState<CacheHealth> & {
  refetch: () => Promise<void>;
  isHealthy: boolean;
  healthStatus: 'healthy' | 'warning' | 'critical';
} {
  const apiClient = useRef<CacheAwareAPIClient | null>(null);
  const [state, setState] = useState<APIRequestState<CacheHealth>>({
    data: null,
    loading: true,
    error: null
  });

  useEffect(() => {
    if (!apiClient.current) {
      const baseClient = getAPIClient();
      apiClient.current = new CacheAwareAPIClient(baseClient);
    }
  }, []);

  const fetchHealth = useCallback(async () => {
    if (!apiClient.current) return;

    setState(prev => ({ ...prev, loading: true }));

    try {
      const data = await apiClient.current.getCacheHealth();
      if (data) {
        setState({
          data,
          loading: false,
          error: null
        });
      } else {
        setState({
          data: null,
          loading: false,
          error: 'Failed to fetch cache health'
        });
      }
    } catch (error) {
      setState({
        data: null,
        loading: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 10000); // Refresh every 10 seconds
    return () => clearInterval(interval);
  }, [fetchHealth]);

  const isHealthy = state.data?.healthy ?? false;
  const healthStatus = state.data?.healthy ? 'healthy' : 'critical';

  return {
    ...state,
    refetch: fetchHealth,
    isHealthy,
    healthStatus
  };
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
    const baseURL = config?.baseURL ?? import.meta.env.VITE_API_URL ?? 'http://localhost:8765';

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
