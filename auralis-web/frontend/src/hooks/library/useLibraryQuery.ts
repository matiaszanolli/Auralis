/**
 * useLibraryQuery Hook
 * ~~~~~~~~~~~~~~~~~~~~
 *
 * Provides type-safe library queries for tracks, albums, and artists.
 * Handles pagination, search, and infinite scroll patterns.
 *
 * Usage:
 * ```typescript
 * // Get tracks with pagination
 * const { data, isLoading, error, fetchMore, hasMore } = useLibraryQuery('tracks', {
 *   limit: 50,
 *   search: 'beatles'
 * });
 *
 * // Get albums
 * const albums = useLibraryQuery('albums', { limit: 20 });
 *
 * // Get artists
 * const artists = useLibraryQuery('artists');
 * ```
 *
 * Features:
 * - Type-safe queries for tracks, albums, artists
 * - Pagination with limit/offset
 * - Search support
 * - Infinite scroll with fetchMore() + hasMore flag
 * - Auto-fetch on mount
 * - Caching with deduplication
 * - Error handling with retry
 *
 * @module hooks/library/useLibraryQuery
 */

import { useCallback, useEffect, useState, useRef } from 'react';
import { useRestAPI } from '@/hooks/api/useRestAPI';
import type { ApiError } from '@/types/api';
import type { Track, Album, Artist } from '@/types/domain';
import { ApiErrorHandler } from '@/types/api';
import { transformAlbums, transformArtists } from '@/api/transformers';
import type { AlbumApiResponse, ArtistApiResponse } from '@/api/transformers';

/**
 * Query type for library queries
 */
export type LibraryQueryType = 'tracks' | 'albums' | 'artists';

/**
 * Query options for library queries
 */
export interface LibraryQueryOptions {
  /** Maximum results per page (default: 50) */
  limit?: number;

  /** Offset for pagination (default: 0) */
  offset?: number;

  /** Search query string */
  search?: string;

  /** Field to order by (default: 'created_at') */
  orderBy?: string;

  /** Skip initial fetch (for manual triggers) */
  skip?: boolean;

  /** Custom endpoint (overrides default) */
  endpoint?: string;
}

/**
 * Response data from library query
 */
export interface LibraryQueryResponse<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
  hasMore: boolean;
}

/**
 * Return type for useLibraryQuery hook
 */
export interface UseLibraryQueryResult<T> {
  /** Query results (tracks, albums, or artists) */
  data: T[];

  /** Total count of items matching query */
  total: number;

  /** True while initial fetch is in progress */
  isLoading: boolean;

  /** True while fetchMore pagination request is in progress */
  isLoadingMore: boolean;

  /** Last error from query */
  error: ApiError | null;

  /** Current offset in pagination */
  offset: number;

  /** Whether more results are available */
  hasMore: boolean;

  /** Fetch next page (for infinite scroll) */
  fetchMore: () => Promise<void>;

  /** Reset query and refetch */
  refetch: () => Promise<void>;

  /** Clear error state */
  clearError: () => void;
}

/**
 * Canonical backend endpoint for each query type (issue #2379).
 *
 * - tracks → /api/library/tracks  (library router)
 * - albums → /api/albums          (albums router — NOT /api/library/albums)
 * - artists → /api/artists        (artists router — NOT /api/library/artists)
 */
const QUERY_TYPE_ENDPOINT: Record<LibraryQueryType, string> = {
  tracks: '/api/library/tracks',
  albums: '/api/albums',
  artists: '/api/artists',
};

/**
 * Hook for querying library (tracks, albums, artists)
 *
 * @param queryType Type of query: 'tracks', 'albums', or 'artists'
 * @param options Query options (limit, offset, search, etc.)
 * @returns Query result with data, loading state, pagination, and methods
 *
 * @example
 * ```typescript
 * // Get first 50 tracks
 * const { data: tracks, isLoading, hasMore, fetchMore } = useLibraryQuery('tracks');
 *
 * // Search tracks
 * const { data: results } = useLibraryQuery('tracks', { search: 'beatles' });
 *
 * // Infinite scroll
 * const { data: items, hasMore, fetchMore } = useLibraryQuery('tracks', { limit: 20 });
 * const handleScroll = () => {
 *   if (hasMore && !isLoading) {
 *     fetchMore();
 *   }
 * };
 * ```
 */
export function useLibraryQuery<T extends Track | Album | Artist = Track>(
  queryType: LibraryQueryType = 'tracks',
  options: LibraryQueryOptions = {}
): UseLibraryQueryResult<T> {
  // Destructure the stable `get` from useRestAPI's stableMethods. The api
  // wrapper object itself is re-memoized on every isLoading/error change, so
  // depending on the whole object churned executeQuery/fetchMore each fetch
  // cycle and re-fired the auto-fetch effect after completion — a latent
  // refetch loop (#4164). `get` is referentially stable.
  const { get } = useRestAPI();

  // State
  const [data, setData] = useState<T[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(options.offset || 0);
  const [isLoading, setIsLoading] = useState(!options.skip);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  // Refs for tracking ongoing requests and query stability
  // Note: request cancellation is handled by useRestAPI's own AbortController.
  const queryKeyRef = useRef<string>('');
  const isFetchingRef = useRef<boolean>(false);
  const isFetchingMoreRef = useRef<boolean>(false);

  // Constants
  const limit = options.limit || 50;
  const skip = options.skip || false;
  const hasMore = (offset + data.length) < total;

  /**
   * Extract items from response based on query type
   * Backend returns type-specific field names: tracks, albums, artists
   *
   * #3631: `response` typed as Record<string, unknown> (was `any`) and the
   * switch is exhaustive via a `never` assertion so adding a new
   * LibraryQueryType triggers a TS error here instead of silently falling
   * through to `response.items`.
   */
  const extractItemsFromResponse = useCallback(
    (response: LibraryQueryResponse<T> | Record<string, unknown>, qType: LibraryQueryType): T[] => {
      const r = response as Record<string, unknown>;
      // Re-assigned locally so the type narrows for the switch below
      // (LibraryQueryResponse<T> has no index signature).
      response = r;
      switch (qType) {
        case 'tracks':
          return ((response.tracks ?? response.items) as T[]) || [];
        case 'albums':
          // Canonical transformer is the single source of truth for snake→camel
          // album mapping (incl. artworkUrl/artistId); no inline variant (#4418).
          return transformAlbums(
            (response.albums ?? response.items ?? []) as AlbumApiResponse[]
          ) as T[];
        case 'artists':
          // Canonical transformer maps every field incl. artworkUrl/dateAdded (#4418).
          return transformArtists(
            (response.artists ?? response.items ?? []) as ArtistApiResponse[]
          ) as T[];
        default: {
          const _exhaustive: never = qType;
          throw new Error(`Unhandled LibraryQueryType: ${String(_exhaustive)}`);
        }
      }
    },
    []
  );

  /**
   * Build endpoint from query type and options
   * Takes offset as a parameter to avoid dependency cycle
   */
  const buildEndpoint = useCallback((currentOffset: number = 0): string => {
    const endpoint = options.endpoint;
    if (endpoint) return endpoint;

    const baseUrl = QUERY_TYPE_ENDPOINT[queryType];
    const params = new URLSearchParams();

    params.append('limit', String(limit || 50));
    params.append('offset', String(currentOffset ?? 0));

    if (options.search) {
      params.append('search', options.search);
    }

    if (options.orderBy) {
      params.append('order_by', options.orderBy);
    }

    return `${baseUrl}?${params.toString()}`;
  }, [queryType, limit, options.endpoint, options.search, options.orderBy]);

  /**
   * Execute query
   */
  const executeQuery = useCallback(
    async (targetOffset: number = 0, append: boolean = false) => {
      const url = buildEndpoint(targetOffset);

      // Generate query key for deduplication
      const queryKey = `${queryType}:${url}:${targetOffset}`;

      // Skip if same query already in flight (use ref to avoid stale closure)
      if (queryKeyRef.current === queryKey && isFetchingRef.current) {
        return;
      }

      queryKeyRef.current = queryKey;
      isFetchingRef.current = true;

      setIsLoading(true);
      setError(null);

      try {
        const response = await get<LibraryQueryResponse<T>>(url);

        if (!response) {
          throw new Error('No response from server');
        }

        const items = extractItemsFromResponse(response, queryType);
        setTotal(response.total || 0);
        setOffset(typeof response.offset === 'number' ? response.offset : 0);

        if (append) {
          // Append to existing data (infinite scroll)
          setData(prev => [...prev, ...items]);
        } else {
          // Replace data (first load or refetch)
          setData(items);
        }
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          // Request was cancelled - don't update state
          return;
        }

        const apiError = ApiErrorHandler.parseWithCode(err, 'QUERY_ERROR');

        setError(apiError);
      } finally {
        isFetchingRef.current = false;
        setIsLoading(false);
      }
    },
    [get, buildEndpoint, queryType]
  );

  /**
   * Fetch next page (for infinite scroll)
   * Includes deduplication to prevent concurrent fetch requests
   */
  const fetchMore = useCallback(async (): Promise<void> => {
    // Guard: Skip if already fetching, no more items, or query in flight
    if (isFetchingMoreRef.current || !hasMore || isFetchingRef.current) {
      return;
    }

    // Mark as fetching to prevent concurrent calls
    isFetchingMoreRef.current = true;
    setIsLoadingMore(true);

    const nextOffset = offset + limit;

    try {
      const response = await get<LibraryQueryResponse<T>>(buildEndpoint(nextOffset));

      if (response) {
        const items = extractItemsFromResponse(response, queryType);
        // Only advance the offset when the page actually returned rows.
        // An empty response must not advance the cursor or it permanently
        // skips `limit` records on the next fetchMore (#3973 / HC-10).
        if (items.length > 0) {
          setOffset(nextOffset);
          setData(prev => [...prev, ...items]);
        }
        setTotal(response.total);
      }
    } catch (err) {
      const apiError = ApiErrorHandler.parseWithCode(err, 'FETCH_MORE_ERROR');

      setError(apiError);
    } finally {
      // Always clear the fetching flags
      isFetchingMoreRef.current = false;
      setIsLoadingMore(false);
    }
  }, [get, offset, limit, hasMore, buildEndpoint, extractItemsFromResponse]);

  /**
   * Refetch - Reset and fetch from beginning
   */
  const refetch = useCallback(async (): Promise<void> => {
    setOffset(0);
    setData([]);
    await executeQuery(0, false);
  }, [executeQuery]);

  /**
   * Clear error
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  /**
   * Auto-fetch on mount or when query parameters change
   */
  useEffect(() => {
    if (skip) return;

    executeQuery(0, false);

    return () => {
      // Cleanup handled by useRestAPI's own unmount abort
    };
  }, [queryType, skip, options.search, options.orderBy, options.limit, options.endpoint, executeQuery]);

  return {
    data,
    total,
    isLoading,
    isLoadingMore,
    error,
    offset,
    hasMore,
    fetchMore,
    refetch,
    clearError,
  };
}

/**
 * Convenience hook for track queries only
 *
 * @example
 * ```typescript
 * const { data: tracks, hasMore, fetchMore } = useTracksQuery({
 *   search: 'beatles',
 *   limit: 50
 * });
 * ```
 */
export function useTracksQuery(options?: LibraryQueryOptions) {
  return useLibraryQuery<Track>('tracks', options);
}

/**
 * Convenience hook for album queries only
 *
 * @example
 * ```typescript
 * const { data: albums } = useAlbumsQuery({ limit: 20 });
 * ```
 */
export function useAlbumsQuery(options?: LibraryQueryOptions) {
  return useLibraryQuery<Album>('albums', options);
}

/**
 * Convenience hook for artist queries only
 *
 * @example
 * ```typescript
 * const { data: artists } = useArtistsQuery();
 * ```
 */
export function useArtistsQuery(options?: LibraryQueryOptions) {
  return useLibraryQuery<Artist>('artists', options);
}

/**
 * Hook for infinite scroll pagination
 *
 * Automatically manages fetching and appending more items as user scrolls.
 *
 * @example
 * ```typescript
 * const { items, isLoading, hasMore, getMoreItems } = useInfiniteScroll(
 *   'tracks',
 *   { limit: 50 }
 * );
 *
 * // In scroll handler:
 * const handleScroll = () => {
 *   if (hasMore && !isLoading) {
 *     getMoreItems();
 *   }
 * };
 * ```
 */
export function useInfiniteScroll<T extends Track | Album | Artist = Track>(
  queryType: LibraryQueryType,
  options?: LibraryQueryOptions
) {
  const { data, isLoading, isLoadingMore, error, hasMore, fetchMore, clearError } = useLibraryQuery<T>(
    queryType,
    { ...options, skip: options?.skip ?? false }
  );

  return {
    items: data,
    isLoading,
    isLoadingMore,
    error,
    hasMore,
    getMoreItems: fetchMore,
    clearError,
  };
}
