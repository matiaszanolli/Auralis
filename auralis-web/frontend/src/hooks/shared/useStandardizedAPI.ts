/**
 * Cache telemetry hooks — `useCacheStats` / `useCacheHealth`
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * React-Query-backed polling hooks over the cache-monitoring endpoints,
 * built on `CacheAwareAPIClient` (envelope unwrap + shared response cache).
 * These are NOT a generic REST client — use `useRestAPI`
 * (hooks/api/useRestAPI.ts) for plain GET/POST/PUT/PATCH/DELETE.
 *
 * History: this module used to also host a generic fetch-on-mount hook (#4300,
 * migrated to `useRestAPI`) plus `usePaginatedAPI` / `useBatchOperations` /
 * `useInitializeAPI`, which had no production consumers and were removed
 * (streamlining #7). The pagination/batch surface of `StandardizedAPIClient`
 * went with them; only the cache-telemetry path remains.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { useCallback, useMemo, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  CacheAwareAPIClient,
  CacheStats,
  CacheHealth,
  getAPIClient,
} from '@/services/api/standardizedAPIClient';

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
