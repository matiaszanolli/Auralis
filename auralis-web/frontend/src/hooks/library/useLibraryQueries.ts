/**
 * Convenience wrappers around useLibraryQuery.
 *
 * Split out of useLibraryQuery.ts (#5478) so the core hook file holds only
 * the shared query machinery. Only useArtistsQuery has a production caller
 * (CozyArtistList); the tracks/albums wrappers and useInfiniteScroll had none
 * and were removed (#6287) — use useLibraryQuery('tracks' | 'albums') directly.
 *
 * @module hooks/library/useLibraryQueries
 */

import { useLibraryQuery, type LibraryQueryOptions } from './useLibraryQuery';

/**
 * Convenience hook for artist queries only
 *
 * @example
 * ```typescript
 * const { data: artists } = useArtistsQuery();
 * ```
 */
export function useArtistsQuery(options?: LibraryQueryOptions) {
  return useLibraryQuery('artists', options);
}
