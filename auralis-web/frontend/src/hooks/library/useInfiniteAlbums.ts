/**
 * useInfiniteAlbums Hook
 *
 * Modern infinite scroll implementation using TanStack Query.
 * Replaces custom useAlbumsQuery + useInfiniteScroll pattern.
 *
 * Uses transformation layer to convert backend snake_case to frontend camelCase.
 *
 * @module hooks/library/useInfiniteAlbums
 */

import { useInfiniteQuery } from '@tanstack/react-query';
import { transformAlbumsResponse } from '@/api/transformers';
import type { AlbumsApiResponse } from '@/api/transformers';
import { API_BASE_URL as API_BASE } from '@/config/api';

interface UseInfiniteAlbumsOptions {
  limit?: number;
  search?: string;
  enabled?: boolean;
}

/**
 * Fetch albums from the API with pagination
 * Returns RAW backend response (snake_case) - will be transformed by useInfiniteAlbums
 */
async function fetchAlbums({
  pageParam = 0,
  limit = 50,
  search,
}: {
  pageParam?: number;
  limit?: number;
  search?: string;
}): Promise<AlbumsApiResponse> {
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

  // Return raw API response (snake_case) - transformation happens in useInfiniteAlbums
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
 * - Automatic snake_case → camelCase transformation
 *
 * @example
 * ```tsx
 * const { data, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfiniteAlbums();
 *
 * // All albums across all pages (camelCase domain models)
 * const allAlbums = data?.pages.flatMap(page => page.albums) ?? [];
 *
 * // Access transformed data
 * allAlbums[0].trackCount // ✅ camelCase
 * allAlbums[0].artworkUrl // ✅ camelCase
 * allAlbums[0].totalDuration // ✅ camelCase
 *
 * // Load more when scrolling
 * <button onClick={() => fetchNextPage()}>Load More</button>
 * ```
 */
export function useInfiniteAlbums(options: UseInfiniteAlbumsOptions = {}) {
  const { limit = 50, search, enabled = true } = options;

  return useInfiniteQuery({
    queryKey: ['albums', { search, limit }],
    queryFn: async ({ pageParam }) => {
      // Fetch raw API response (snake_case)
      const apiResponse = await fetchAlbums({
        pageParam,
        limit,
        search,
      });

      // Transform to domain model (camelCase)
      return transformAlbumsResponse(apiResponse);
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage) => {
      // lastPage is now transformed response with hasMore (camelCase)
      return lastPage.hasMore ? lastPage.offset + lastPage.limit : undefined;
    },
    enabled,
  });
}
