/**
 * Cache telemetry hooks — `useCacheStats` / `useCacheHealth`
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * React-Query-backed polling hooks over the cache-monitoring endpoints.
 * These are NOT a generic REST client — use `useRestAPI`
 * (hooks/api/useRestAPI.ts) for plain GET/POST/PUT/PATCH/DELETE.
 *
 * #4693: these used to go through `CacheAwareAPIClient`, the app's third
 * parallel HTTP layer. They now use `utils/apiRequest.ts` like everything
 * else, with the `isCacheStatsShape` / `isCacheHealthShape` guards (#4440)
 * carried over as `apiRequest`'s `validate` step — same contract: a bare
 * payload (these endpoints send no envelope), and a throw rather than a silent
 * `null` on a wrong shape or an HTTP error.
 *
 * Retiring that client also removed a second, redundant response cache sitting
 * underneath React Query. It had a 60s TTL and cached every GET, while
 * `useCacheStats` polls every 5s — so eleven of every twelve polls returned a
 * cached value, `refetch()` could return data up to a minute old, and the
 * `cache_cleared` invalidation below (#4585) was partly defeated because
 * invalidating the React Query entry still hit the stale inner cache.
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
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  CacheStats,
  CacheHealth,
  isCacheStatsShape,
  isCacheHealthShape,
} from '@/services/api/standardizedAPIClient';
import { get } from '@/utils/apiRequest';
import { useWebSocketMessages } from '@/hooks/websocket/useWebSocketMessages';
import type { WebSocketMessageType } from '@/types/websocket';

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

// Single source of truth for useCacheStats' poll cadence — also consumed by
// CacheStatsDashboard's footer label so the two can't drift out of sync (#4310).
export const CACHE_STATS_REFRESH_INTERVAL_MS = 5000;

// Module-level constant so the subscription key is referentially stable.
const CACHE_CLEARED_TYPES: WebSocketMessageType[] = ['cache_cleared'];

/**
 * Refresh cache telemetry when the backend broadcasts `cache_cleared` (#4585).
 *
 * `POST /api/cache/clear` empties both tiers, which invalidates every
 * `['cache', …]` query at once — including for clients that did not initiate
 * the clear. Before this, the broadcast had no frontend subscriber at all and
 * the dashboards showed stale "cached" figures until their next poll (5 s for
 * stats, 10 s for health) or a remount.
 *
 * Invalidating the shared `['cache']` prefix means one subscriber covers every
 * cache query; React Query refetches only the observers that are mounted, and
 * a failed refetch surfaces through each hook's existing `error` field.
 */
function useCacheClearedInvalidation(): void {
  const queryClient = useQueryClient();

  useWebSocketMessages(
    CACHE_CLEARED_TYPES,
    useCallback(() => {
      void queryClient.invalidateQueries({ queryKey: ['cache'] });
    }, [queryClient])
  );
}

/**
 * Hook for monitoring cache statistics (#2806: React Query for dedup)
 */
export function useCacheStats(): APIRequestState<CacheStats> & {
  refetch: () => Promise<void>;
} {
  const query = useQuery<CacheStats | null>({
    queryKey: ['cache', 'stats'],
    queryFn: () => get<CacheStats>('/api/cache/stats', { validate: isCacheStatsShape }),
    refetchInterval: CACHE_STATS_REFRESH_INTERVAL_MS,
  });

  useCacheClearedInvalidation();

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
    queryFn: () => get<CacheHealth>('/api/cache/health', { validate: isCacheHealthShape }),
    refetchInterval: refreshInterval,
  });

  useCacheClearedInvalidation();

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
