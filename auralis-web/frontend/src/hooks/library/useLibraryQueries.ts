/**
 * Convenience wrappers around useLibraryQuery.
 *
 * Split out of useLibraryQuery.ts (#5478) so the core hook file holds only
 * the shared query machinery. Only useArtistsQuery is
 * wrapped (CozyArtistList calls it); for tracks or albums use
 * useLibraryQuery('tracks' | 'albums') directly. Do not add a wrapper without
 * a production caller (#6287).
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
