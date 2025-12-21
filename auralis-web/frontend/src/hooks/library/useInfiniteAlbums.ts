/**
 * useInfiniteAlbums Hook
 *
 * Modern infinite scroll implementation using TanStack Query.
 * Replaces custom useAlbumsQuery + useInfiniteScroll pattern.
 *
 * @module hooks/library/useInfiniteAlbums
 */

import { useInfiniteQuery } from '@tanstack/react-query';
import type { Album } from '@/types/domain';

interface AlbumsResponse {
  albums: Album[];
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
}

interface UseInfiniteAlbumsOptions {
  limit?: number;
  search?: string;
  enabled?: boolean;
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8765';

/**
 * Fetch albums from the API with pagination
 */
async function fetchAlbums({
  pageParam = 0,
  limit = 50,
  search,
}: {
  pageParam?: number;
  limit?: number;
  search?: string;
}): Promise<AlbumsResponse> {
  const params = new URLSearchParams({
    offset: pageParam.toString(),
    limit: limit.toString(),
  });

  if (search) {
    params.append('search', search);
  }

  const response = await fetch(`${API_BASE}/api/albums?${params}`);

  if (!response.ok) {
    throw new Error(`Failed to fetch albums: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Use infinite albums query
 *
 * Provides battle-tested infinite scroll with built-in:
 * - Request deduplication
 * - Automatic refetching
 * - Cache management
 * - Loading states
 *
 * @example
 * ```tsx
 * const { data, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfiniteAlbums();
 *
 * // All albums across all pages
 * const allAlbums = data?.pages.flatMap(page => page.albums) ?? [];
 *
 * // Load more when scrolling
 * <button onClick={() => fetchNextPage()}>Load More</button>
 * ```
 */
export function useInfiniteAlbums(options: UseInfiniteAlbumsOptions = {}) {
  const { limit = 50, search, enabled = true } = options;

  return useInfiniteQuery({
    queryKey: ['albums', { search, limit }],
    queryFn: ({ pageParam }) =>
      fetchAlbums({
        pageParam,
        limit,
        search,
      }),
    initialPageParam: 0,
    getNextPageParam: (lastPage) => {
      return lastPage.has_more ? lastPage.offset + lastPage.limit : undefined;
    },
    enabled,
  });
}
