/**
 * The three request paths of useLibraryQuery - first page / re-query, next page, in-place refresh
 * - and the request bookkeeping they share (#6275).
 *
 * All three draw ids from one `useLatestRequestGuard` and one `useSupersedingAbort`, so any newer
 * request makes every older one discard its response (#4609, #4885) and abort its HTTP call
 * (#5650). That shared bookkeeping is why they live together; useLibraryQuery keeps the state and
 * the auto-fetch effect and hands the fetchers its setters.
 *
 * @module hooks/library/useLibraryQueryFetchers
 */

import { useCallback, useRef } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import { useRestAPI } from '@/hooks/api/useRestAPI';
import { useLatestRequestGuard } from '@/hooks/shared/useLatestRequestGuard';
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
  type LibraryQueryType,
} from '@/hooks/library/libraryQueryTypes';

type Setter<T> = Dispatch<SetStateAction<T>>;

/** The slice of useLibraryQuery's state the fetchers read and write. */
export interface LibraryQueryStateView<Q extends LibraryQueryType> {
  offset: number;
  hasMore: boolean;
  dataLength: number;
  setData: Setter<LibraryItemByQuery[Q][]>;
  setTotal: Setter<number>;
  setOffset: Setter<number>;
  setHasMore: Setter<boolean>;
  setIsLoading: Setter<boolean>;
  setIsLoadingMore: Setter<boolean>;
  setError: Setter<ApiError | null>;
  setLoadMoreError: Setter<ApiError | null>;
}

export function useLibraryQueryFetchers<Q extends LibraryQueryType>(
  queryType: Q,
  endpointOptions: Parameters<typeof buildQueryEndpoint>[1],
  limit: number,
  view: LibraryQueryStateView<Q>
) {
  // Only the referentially stable `get`: depending on the whole api object (re-memoized on every
  // isLoading/error change) re-fired the auto-fetch effect after each completion (#4164).
  const { get } = useRestAPI();
  const {
    offset, hasMore, setData, setTotal, setOffset, setHasMore,
    setIsLoading, setIsLoadingMore, setError, setLoadMoreError,
  } = view;

  const queryKeyRef = useRef<string>('');
  const isFetchingRef = useRef<boolean>(false);
  const isFetchingMoreRef = useRef<boolean>(false);
  // Monotonic request id guarding against out-of-order responses (#4609): the URL-keyed dedup never
  // fires across searches, so request A ("be") resolving after B ("bea") overwrote B's results. A
  // ref, not an effect-scoped flag (#3925), because fetchMore/refresh drive requests directly.
  const beginRequest = useLatestRequestGuard();
  const claimRequest = useSupersedingAbort(); // aborts the superseded HTTP request (#5650)
  const dataLengthRef = useRef(0); // sizes refresh() without a `data` dependency
  dataLengthRef.current = view.dataLength;

  /** Execute query */
  const executeQuery = useCallback(
    async (targetOffset: number = 0, append: boolean = false) => {
      const url = buildQueryEndpoint(queryType, endpointOptions, targetOffset);

      // Skip if the same query is already in flight (ref: no stale closure)
      const queryKey = `${queryType}:${url}:${targetOffset}`;
      if (queryKeyRef.current === queryKey && isFetchingRef.current) return;

      queryKeyRef.current = queryKey;
      isFetchingRef.current = true;

      // Claim this request. Any later call supersedes it, and every state setter below is gated on
      // still being the newest (#4609).
      const isStale = beginRequest();
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
        // Only the newest request owns the shared in-flight/loading state. Clearing it from a
        // superseded request would drop the spinner while the current query is still running (#4609).
        if (!isStale()) {
          isFetchingRef.current = false;
          setIsLoading(false);
        }
      }
    },
    [get, queryType, endpointOptions, claimRequest, beginRequest, setIsLoading, setError, setLoadMoreError, setTotal, setOffset, setHasMore, setData]
  );

  /** Fetch next page (infinite scroll), deduplicated against concurrent calls */
  const fetchMore = useCallback(async (): Promise<void> => {
    if (isFetchingMoreRef.current || !hasMore || isFetchingRef.current) return;

    // Mark as fetching to prevent concurrent calls; a retry clears the last failure.
    isFetchingMoreRef.current = true;
    setIsLoadingMore(true);
    setLoadMoreError(null);

    // Share executeQuery's request id (#4885): the guards above only cover this call's start, not a
    // newer query (a search change) replacing `data` while this page is in flight.
    const isStale = beginRequest();
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
      // Only advance the offset when the page actually returned rows. An empty response must not
      // advance the cursor or it permanently skips `limit` records on the next fetchMore (#3973).
      if (items.length > 0) {
        setOffset(nextOffset);
        setData(prev => [...prev, ...items]);
      }
      setTotal(response.total);
      setHasMore(deriveHasMore(response, nextOffset, items.length));
    } finally {
      // Always clear these, stale or not: unlike executeQuery's shared flags they belong solely to
      // fetchMore, and leaving them set on a superseded call would lock out every future fetchMore().
      isFetchingMoreRef.current = false;
      setIsLoadingMore(false);
    }
  }, [get, offset, limit, hasMore, queryType, endpointOptions, claimRequest, beginRequest, setIsLoadingMore, setLoadMoreError, setOffset, setData, setTotal, setHasMore]);

  /**
   * Refresh in place (#5871): re-read the loaded pages so a library change updates the rows without
   * dropping back to page 1 like refetch(). A failed refresh keeps the current rows; the next
   * change retries.
   */
  const refresh = useCallback(async (): Promise<void> => {
    if (dataLengthRef.current === 0) return executeQuery(0, false);
    const result = await fetchLoadedPages({
      get, queryType, endpointOptions, loaded: dataLengthRef.current,
      isStale: beginRequest(), signal: claimRequest(),
    });
    if (result.kind !== 'refreshed') return;
    setData(result.items);
    setOffset(result.offset);
    setTotal(result.total);
    setHasMore(result.hasMore);
  }, [get, queryType, endpointOptions, claimRequest, beginRequest, executeQuery, setData, setOffset, setTotal, setHasMore]);

  return { executeQuery, fetchMore, refresh };
}
