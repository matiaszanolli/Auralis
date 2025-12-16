/**
 * useAlbumsQuery Hook
 * ~~~~~~~~~~~~~~~~~~~
 *
 * Convenience hook for querying albums from the library.
 * Delegates to useLibraryQuery with type='albums' for consistent behavior.
 *
 * This hook provides a cleaner API for album queries compared to the generic
 * useLibraryQuery('albums', ...) pattern.
 *
 * @example
 * ```typescript
 * // Get albums with pagination
 * const { data, isLoading, fetchMore, hasMore } = useAlbumsQuery({
 *   limit: 20,
 *   search: 'dark side'
 * });
 *
 * // Infinite scroll
 * const albums = useAlbumsQuery();
 * if (albums.hasMore) {
 *   albums.fetchMore();
 * }
 * ```
 *
 * @see useLibraryQuery For the underlying implementation
 * @module hooks/library/useAlbumsQuery
 */

import { useLibraryQuery, LibraryQueryOptions, UseLibraryQueryResult } from './useLibraryQuery';
import type { Album } from '@/types/domain';

/**
 * Query albums from the library with pagination and search support.
 *
 * @param options Query options (limit, offset, search, etc.)
 * @returns Query result with albums data and pagination helpers
 */
export function useAlbumsQuery(options?: LibraryQueryOptions): UseLibraryQueryResult<Album> {
  return useLibraryQuery('albums', options);
}
