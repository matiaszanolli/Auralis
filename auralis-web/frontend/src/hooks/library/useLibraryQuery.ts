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

  /** True while fetch is in progress */
  isLoading: boolean;

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
  const api = useRestAPI();

  // State
  const [data, setData] = useState<T[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(options.offset || 0);
  const [isLoading, setIsLoading] = useState(!options.skip);
  const [error, setError] = useState<ApiError | null>(null);

  // Refs for tracking ongoing requests and query stability
  const abortControllerRef = useRef<AbortController | null>(null);
  const queryKeyRef = useRef<string>('');
  const isFetchingMoreRef = useRef<boolean>(false);

  // Constants
  const limit = options.limit || 50;
  const skip = options.skip || false;
  const hasMore = (offset + data.length) < total;

  /**
   * Extract items from response based on query type
   * Backend returns type-specific field names: tracks, albums, artists
   */
  const extractItemsFromResponse = useCallback((response: any, qType: LibraryQueryType): T[] => {
    switch (qType) {
      case 'tracks':
        return response.tracks || response.items || [];
      case 'albums':
        return response.albums || response.items || [];
      case 'artists':
        return response.artists || response.items || [];
      default:
        return response.items || [];
    }
  }, []);

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

      // Skip if same query already in flight
      if (queryKeyRef.current === queryKey && isLoading) {
        return;
      }

      queryKeyRef.current = queryKey;

      // Cancel previous request if any
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      abortControllerRef.current = new AbortController();
      setIsLoading(true);
      setError(null);

      try {
        const response = await api.get<LibraryQueryResponse<T>>(url);

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

        const apiError = err instanceof Error
          ? { message: err.message, code: 'QUERY_ERROR', status: 500 }
          : (err as ApiError);

        setError(apiError);
      } finally {
        setIsLoading(false);
      }
    },
    [api, buildEndpoint, queryType]
  );

  /**
   * Fetch next page (for infinite scroll)
   * Includes deduplication to prevent concurrent fetch requests
   */
  const fetchMore = useCallback(async (): Promise<void> => {
    // Guard: Skip if already fetching, no more items, or currently loading
    if (isFetchingMoreRef.current || !hasMore || isLoading) {
      return;
    }

    // Mark as fetching to prevent concurrent calls
    isFetchingMoreRef.current = true;

    const nextOffset = offset + limit;

    try {
      const response = await api.get<LibraryQueryResponse<T>>(buildEndpoint(nextOffset));

      if (response) {
        const items = extractItemsFromResponse(response, queryType);
        // Only update offset after successful fetch
        setOffset(nextOffset);
        setData(prev => [...prev, ...items]);
        setTotal(response.total);
      }
    } catch (err) {
      const apiError = err instanceof Error
        ? { message: err.message, code: 'FETCH_MORE_ERROR', status: 500 }
        : (err as ApiError);

      setError(apiError);
    } finally {
      // Always clear the fetching flag
      isFetchingMoreRef.current = false;
    }
  }, [api, offset, limit, hasMore, isLoading, buildEndpoint, extractItemsFromResponse]);

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

    // Cleanup on unmount
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryType, skip, options.search, options.orderBy]);

  return {
    data,
    total,
    isLoading,
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
  const { data, isLoading, error, hasMore, fetchMore, clearError } = useLibraryQuery<T>(
    queryType,
    { ...options, skip: options?.skip ?? false }
  );

  return {
    items: data,
    isLoading,
    error,
    hasMore,
    getMoreItems: fetchMore,
    clearError,
  };
}
