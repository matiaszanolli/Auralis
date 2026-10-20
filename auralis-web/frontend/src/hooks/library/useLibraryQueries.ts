/**
 * Convenience wrappers around useLibraryQuery.
 *
 * Split out of useLibraryQuery.ts (#5478) so the core hook file holds only
 * the shared query machinery; these add per-entity sugar and the infinite
 * scroll adapter on top of it.
 *
 * @module hooks/library/useLibraryQueries
 */

import type { Track, Album, Artist } from '@/types/domain';
import { useLibraryQuery, type LibraryQueryOptions, type LibraryQueryType } from './useLibraryQuery';

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
