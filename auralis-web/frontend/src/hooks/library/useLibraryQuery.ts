/**
 * useLibraryQuery Hook
 * ~~~~~~~~~~~~~~~~~~~~
 *
 * Type-safe paginated library queries for tracks, albums, and artists:
 * pagination (limit/offset), search, infinite scroll via fetchMore()/hasMore,
 * auto-fetch on mount, in-flight deduplication, and out-of-order-response
 * protection. See the hook's JSDoc below for usage.
 *
 * The pure request/response shaping and the shared page-fetch machinery live
 * in ./libraryQueryRequest; the query types, shape guards and deriveHasMore
 * in ./libraryQueryTypes; the per-entity convenience hooks
 * (useArtistsQuery) in
 * ./useLibraryQueries — all split out of this file (#5043, #5478). This file
 * holds only the stateful hook.
 *
 * @module hooks/library/useLibraryQuery
 */

import { LIBRARY_PAGE_LIMIT } from '@/config/api';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLibraryQueryFetchers } from './useLibraryQueryFetchers';
import type { ApiError } from '@/types/api';
import {
  type LibraryItemByQuery,
  type LibraryQueryOptions,
  type LibraryQueryType,
  type UseLibraryQueryResult,
} from '@/hooks/library/libraryQueryTypes';

// Re-exported for the existing importers of this module; the definitions
// live in ./libraryQueryTypes (#5478).
export type {
  LibraryQueryType,
  LibraryQueryOptions,
  LibraryQueryResponse,
  UseLibraryQueryResult,
  LibraryItemByQuery,
} from '@/hooks/library/libraryQueryTypes';

/**
 * Hook for querying library (tracks, albums, artists)
 *
 * @param queryType Type of query: 'tracks', 'albums', or 'artists'
 * @param options Query options (limit, offset, search, etc.)
 * @returns Query result with data, loading state, pagination, and methods
 *
 * @example
 * ```typescript
 * const { data: tracks, isLoading, hasMore, fetchMore } = useLibraryQuery('tracks');
 * ```
 */
export function useLibraryQuery<Q extends LibraryQueryType>(
  queryType: Q,
  options: LibraryQueryOptions = {}
): UseLibraryQueryResult<LibraryItemByQuery[Q]> {
  // State
  const [data, setData] = useState<LibraryItemByQuery[Q][]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(options.offset || 0);
  const [isLoading, setIsLoading] = useState(!options.skip);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  // A failed page 2+ is not a failed list: kept apart from `error` so the
  // loaded rows stay on screen behind an inline Retry (#5870).
  const [loadMoreError, setLoadMoreError] = useState<ApiError | null>(null);
  const [hasMore, setHasMore] = useState(false);

  // Constants
  const limit = options.limit || LIBRARY_PAGE_LIMIT;
  const skip = options.skip || false;

  // The option list is exactly what buildQueryEndpoint shapes the URL from,
  // so executeQuery/fetchMore re-memoize precisely when the endpoint would
  // change (the old `buildEndpoint` useCallback bought nothing extra). The
  // memo is load-bearing: a fresh literal each render would re-memoize
  // executeQuery every render and re-fire the auto-fetch effect (#4164).
  const endpointOptions = useMemo(
    () => ({
      limit,
      endpoint: options.endpoint,
      search: options.search,
      orderBy: options.orderBy,
    }),
    [limit, options.endpoint, options.search, options.orderBy]
  );

  const { executeQuery, fetchMore, refresh } = useLibraryQueryFetchers(queryType, endpointOptions, limit, {
    offset, hasMore, dataLength: data.length,
    setData, setTotal, setOffset, setHasMore, setIsLoading, setIsLoadingMore, setError, setLoadMoreError,
  });

  /** Refetch - Reset and fetch from beginning */
  const refetch = useCallback(async (): Promise<void> => {
    setOffset(0);
    setData([]);
    await executeQuery(0, false);
  }, [executeQuery]);

  /** Clear error */
  const clearError = useCallback(() => {
    setError(null);
    setLoadMoreError(null);
  }, []);

  /** Auto-fetch on mount or when query parameters change */
  useEffect(() => {
    if (skip) return;

    executeQuery(0, false);

    // No cleanup needed: useRestAPI aborts on UNMOUNT, and executeQuery aborts
    // the superseded request while mounted (claimRequest, #5650; beginRequest
    // discards its response, #4609).
  }, [queryType, skip, options.search, options.orderBy, options.limit, options.endpoint, executeQuery]);

  return {
    data,
    total,
    isLoading,
    isLoadingMore,
    error,
    loadMoreError,
    offset,
    hasMore,
    fetchMore,
    refetch,
    refresh,
    clearError,
  };
}

// Convenience hooks live in ./useLibraryQueries (#5478); re-exported here so
// existing `from './useLibraryQuery'` imports keep working.
export { useArtistsQuery } from './useLibraryQueries';
