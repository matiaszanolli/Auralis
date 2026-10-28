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
 * (useTracksQuery/useAlbumsQuery/useArtistsQuery/useInfiniteScroll) in
 * ./useLibraryQueries — all split out of this file (#5043, #5478). This file
 * holds only the stateful hook.
 *
 * @module hooks/library/useLibraryQuery
 */

import { LIBRARY_PAGE_LIMIT } from '@/config/api';
import { useCallback, useEffect, useMemo, useState, useRef } from 'react';
import { useRestAPI } from '@/hooks/api/useRestAPI';
import { useSupersedingAbort } from './useSupersedingAbort';
import type { ApiError } from '@/types/api';
import {
  buildEndpoint as buildQueryEndpoint,
  extractItemsFromResponse,
  fetchLibraryPage,
  fetchLoadedPages,
} from '@/hooks/library/libraryQueryRequest';
import {
  QUERY_TYPE_GUARD,
  deriveHasMore,
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
  // Only the referentially stable `get`: depending on the whole api object
  // (re-memoized on every isLoading/error change) re-fired the auto-fetch
  // effect after each completion — a latent refetch loop (#4164).
  const { get } = useRestAPI();

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

  // Refs for tracking ongoing requests and query stability
  const queryKeyRef = useRef<string>('');
  const isFetchingRef = useRef<boolean>(false);
  const isFetchingMoreRef = useRef<boolean>(false);
  // Monotonic request id guarding against out-of-order responses (#4609): the
  // URL-keyed dedup never fires across searches, so request A ("be") resolving
  // after B ("bea") overwrote B's results. A ref, not an effect-scoped flag
  // (#3925), because fetchMore/refetch/refresh drive requests directly.
  const requestIdRef = useRef<number>(0);
  const dataLengthRef = useRef(0); // sizes refresh() without a `data` dependency
  dataLengthRef.current = data.length;
  const claimRequest = useSupersedingAbort(); // aborts the superseded HTTP request (#5650)

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

  /** Execute query */
  const executeQuery = useCallback(
    async (targetOffset: number = 0, append: boolean = false) => {
      const url = buildQueryEndpoint(queryType, endpointOptions, targetOffset);

      // Skip if the same query is already in flight (ref: no stale closure)
      const queryKey = `${queryType}:${url}:${targetOffset}`;
      if (queryKeyRef.current === queryKey && isFetchingRef.current) {
        return;
      }

      queryKeyRef.current = queryKey;
      isFetchingRef.current = true;

      // Claim this request. Any later call supersedes it, and every state
      // setter below is gated on still being the newest (#4609).
      const myRequestId = ++requestIdRef.current;
      const isStale = () => requestIdRef.current !== myRequestId;
      const signal = claimRequest();

      setIsLoading(true);
      setError(null);
      setLoadMoreError(null);

      try {
        const result = await fetchLibraryPage({
          get,
          url,
          validate: QUERY_TYPE_GUARD[queryType],
          isStale,
          errorCode: 'QUERY_ERROR',
          requireResponse: true,
          signal,
        });

        if (result.kind === 'error') {
          setError(result.error);
          return;
        }
        if (result.kind !== 'ok') return; // stale or aborted

        const response = result.response;
        if (!response) return; // unreachable with requireResponse (null became an error above)
        const items = extractItemsFromResponse(response, queryType);
        const newOffset = typeof response.offset === 'number' ? response.offset : 0;
        setTotal(response.total || 0);
        setOffset(newOffset);
        setHasMore(deriveHasMore(response, newOffset, items.length));

        // Append (infinite scroll) or replace (first load / refetch)
        setData(prev => (append ? [...prev, ...items] : items));
      } finally {
        // Only the newest request owns the shared in-flight/loading state.
        // Clearing it from a superseded request would drop the spinner while
        // the current query is still running (#4609 RETURN VALUE check).
        if (!isStale()) {
          isFetchingRef.current = false;
          setIsLoading(false);
        }
      }
    },
    [get, queryType, endpointOptions, claimRequest]
  );

  /** Fetch next page (infinite scroll), deduplicated against concurrent calls */
  const fetchMore = useCallback(async (): Promise<void> => {
    // Guard: Skip if already fetching, no more items, or query in flight
    if (isFetchingMoreRef.current || !hasMore || isFetchingRef.current) {
      return;
    }

    // Mark as fetching to prevent concurrent calls; a retry clears the last failure.
    isFetchingMoreRef.current = true;
    setIsLoadingMore(true);
    setLoadMoreError(null);

    // Share executeQuery's request id (#4885): the guards above only cover
    // this call's start, not a newer query (a search change) replacing `data`
    // while this page is in flight.
    const myRequestId = ++requestIdRef.current;
    const isStale = () => requestIdRef.current !== myRequestId;
    const signal = claimRequest();

    const nextOffset = offset + limit;

    try {
      const result = await fetchLibraryPage({
        get,
        url: buildQueryEndpoint(queryType, endpointOptions, nextOffset),
        validate: QUERY_TYPE_GUARD[queryType],
        isStale,
        errorCode: 'FETCH_MORE_ERROR',
        requireResponse: false,
        signal,
      });

      if (result.kind === 'error') {
        setLoadMoreError(result.error);
        return;
      }
      if (result.kind !== 'ok' || !result.response) return; // stale/aborted/no page

      const response = result.response;
      const items = extractItemsFromResponse(response, queryType);
      // Only advance the offset when the page actually returned rows.
      // An empty response must not advance the cursor or it permanently
      // skips `limit` records on the next fetchMore (#3973 / HC-10).
      if (items.length > 0) {
        setOffset(nextOffset);
        setData(prev => [...prev, ...items]);
      }
      setTotal(response.total);
      setHasMore(deriveHasMore(response, nextOffset, items.length));
    } finally {
      // Always clear these, stale or not: unlike executeQuery's shared flags
      // they belong solely to fetchMore, and leaving them set on a superseded
      // call would lock out every future fetchMore().
      isFetchingMoreRef.current = false;
      setIsLoadingMore(false);
    }
  }, [get, offset, limit, hasMore, queryType, endpointOptions, claimRequest]);

  /**
   * Refresh in place (#5871): re-read the loaded pages so a library change
   * updates the rows without dropping back to page 1 like refetch(). A failed
   * refresh keeps the current rows; the next change retries.
   */
  const refresh = useCallback(async (): Promise<void> => {
    if (dataLengthRef.current === 0) return executeQuery(0, false);
    const myRequestId = ++requestIdRef.current;
    const result = await fetchLoadedPages({
      get, queryType, endpointOptions, loaded: dataLengthRef.current,
      isStale: () => requestIdRef.current !== myRequestId, signal: claimRequest(),
    });
    if (result.kind !== 'refreshed') return;
    setData(result.items);
    setOffset(result.offset);
    setTotal(result.total);
    setHasMore(result.hasMore);
  }, [get, queryType, endpointOptions, claimRequest, executeQuery]);

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
    // the superseded request while mounted (claimRequest, #5650; requestIdRef
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
export { useTracksQuery, useAlbumsQuery, useArtistsQuery, useInfiniteScroll } from './useLibraryQueries';
