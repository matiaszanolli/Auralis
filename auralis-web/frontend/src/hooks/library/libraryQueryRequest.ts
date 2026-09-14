/**
 * Library query request/response shaping
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * The pure half of `useLibraryQuery` (#5043): building a page's endpoint URL
 * and pulling typed items out of a list response. Both used to be
 * `useCallback`s inside the hook body, so exercising them meant mounting the
 * hook — which is how its tests drifted toward testing the mock instead of
 * the pagination and shaping logic (#4963). As plain functions of their
 * arguments they are unit-tested directly.
 *
 * @module hooks/library/libraryQueryRequest
 */

import type { Track, Album, Artist } from '@/types/domain';
import { transformAlbums, transformArtists, transformTracks } from '@/api/transformers';
import type { AlbumApiResponse, ArtistApiResponse, TrackApiResponse } from '@/api/transformers';
import type {
  LibraryQueryOptions,
  LibraryQueryResponse,
  LibraryQueryType,
} from '@/hooks/library/useLibraryQuery';

/**
 * Canonical backend endpoint for each query type (issue #2379).
 *
 * - tracks → /api/library/tracks  (library router)
 * - albums → /api/albums          (albums router — NOT /api/library/albums)
 * - artists → /api/artists        (artists router — NOT /api/library/artists)
 */
export const QUERY_TYPE_ENDPOINT: Record<LibraryQueryType, string> = {
  tracks: '/api/library/tracks',
  albums: '/api/albums',
  artists: '/api/artists',
};

/** The query options that shape the request URL. */
export type EndpointOptions = Pick<LibraryQueryOptions, 'limit' | 'search' | 'orderBy' | 'endpoint'>;

/**
 * Build the URL for one page of a library query.
 *
 * A custom `options.endpoint` is used verbatim. Otherwise the query type's
 * canonical endpoint gets `limit` (default 50) and `offset`, plus `search` and
 * `order_by` when set.
 */
export function buildEndpoint(
  queryType: LibraryQueryType,
  options: EndpointOptions,
  offset: number = 0
): string {
  if (options.endpoint) return options.endpoint;

  const params = new URLSearchParams();
  params.append('limit', String(options.limit || 50));
  params.append('offset', String(offset ?? 0));

  if (options.search) {
    params.append('search', options.search);
  }

  if (options.orderBy) {
    params.append('order_by', options.orderBy);
  }

  return `${QUERY_TYPE_ENDPOINT[queryType]}?${params.toString()}`;
}

/**
 * Extract items from a list response based on query type.
 *
 * The backend returns type-specific field names (`tracks`, `albums`,
 * `artists`), with `items` as the fallback, and every list goes through its
 * canonical snake→camel transformer.
 *
 * #3631: `response` is typed as a record (was `any`) and the switch is
 * exhaustive via a `never` assertion, so adding a new LibraryQueryType is a TS
 * error here instead of silently falling through to `response.items`.
 */
export function extractItemsFromResponse<T extends Track | Album | Artist>(
  response: LibraryQueryResponse<T> | Record<string, unknown>,
  queryType: LibraryQueryType
): T[] {
  // LibraryQueryResponse<T> has no index signature, so narrow to a record.
  const r = response as Record<string, unknown>;
  switch (queryType) {
    case 'tracks':
      // Canonical transformer, matching albums/artists below. Previously a
      // raw cast with zero field conversion, so every camelCase-only field
      // (artworkUrl/sampleRate/bitDepth/dateAdded/...) came back undefined
      // against the backend's snake_case payload — silently, with a passing
      // type-check. #4418 added transformers here but skipped 'tracks' (#4611).
      return transformTracks((r.tracks ?? r.items ?? []) as TrackApiResponse[]) as T[];
    case 'albums':
      // Canonical transformer is the single source of truth for snake→camel
      // album mapping (incl. artworkUrl/artistId); no inline variant (#4418).
      return transformAlbums((r.albums ?? r.items ?? []) as AlbumApiResponse[]) as T[];
    case 'artists':
      // Canonical transformer maps every field incl. artworkUrl/dateAdded (#4418).
      return transformArtists((r.artists ?? r.items ?? []) as ArtistApiResponse[]) as T[];
    default: {
      const _exhaustive: never = queryType;
      throw new Error(`Unhandled LibraryQueryType: ${String(_exhaustive)}`);
    }
  }
}
