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

import { ENDPOINTS, LIBRARY_PAGE_LIMIT } from '@/config/api';
import { transformAlbums, transformArtists, transformTracks } from '@/api/transformers';
import type { AlbumApiResponse, ArtistApiResponse, TrackApiResponse } from '@/api/transformers';
import { ApiErrorHandler } from '@/types/api';
import type { ApiError } from '@/types/api';
import type {
  LibraryItemByQuery,
  LibraryQueryOptions,
  LibraryQueryResponse,
  LibraryQueryType,
} from './libraryQueryTypes';

/**
 * Canonical backend endpoint for each query type (issue #2379).
 *
 * - tracks → /api/library/tracks  (library router)
 * - albums → /api/albums          (albums router — NOT /api/library/albums)
 * - artists → /api/artists        (artists router — NOT /api/library/artists)
 */
export const QUERY_TYPE_ENDPOINT: Record<LibraryQueryType, string> = {
  // Derived from ENDPOINTS (#6217) — the paths were re-typed here and could
  // drift from the catalog in config/api.ts.
  tracks: ENDPOINTS.LIBRARY_TRACKS,
  albums: ENDPOINTS.LIBRARY_ALBUMS,
  artists: ENDPOINTS.LIBRARY_ARTISTS,
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
  params.append('limit', String(options.limit || LIBRARY_PAGE_LIMIT));
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
 * Per-type extractor. The mapped type makes the table exhaustive (a new
 * LibraryQueryType without an entry is a TS error, #3631) and ties each
 * extractor's result to `LibraryItemByQuery`, so no `as T[]` is needed (#6054).
 * Each arm reads the collection key its own guard has already verified at the
 * boundary (#5637); the `as XApiResponse[]` casts are that wire boundary.
 */
const EXTRACT_ITEMS: {
  [Q in LibraryQueryType]: (r: Record<string, unknown>) => LibraryItemByQuery[Q][];
} = {
  // Canonical transformer, matching albums/artists below. Previously a
  // raw cast with zero field conversion, so every camelCase-only field
  // (artworkUrl/sampleRate/bitDepth/dateAdded/...) came back undefined
  // against the backend's snake_case payload — silently, with a passing
  // type-check. #4418 added transformers here but skipped 'tracks' (#4611).
  tracks: (r) => transformTracks((r.tracks ?? []) as TrackApiResponse[]),
  // Canonical transformer is the single source of truth for snake→camel
  // album mapping (incl. artworkUrl/artistId); no inline variant (#4418).
  albums: (r) => transformAlbums((r.albums ?? []) as AlbumApiResponse[]),
  // Canonical transformer maps every field incl. artworkUrl/dateAdded (#4418).
  artists: (r) => transformArtists((r.artists ?? []) as ArtistApiResponse[]),
};

/**
 * Extract items from a list response based on query type.
 *
 * The backend returns type-specific field names (`tracks`, `albums`,
 * `artists`) and every list goes through its canonical snake→camel
 * transformer; there is no generic `items` fallback. The result type follows
 * `queryType` through `LibraryItemByQuery`.
 */
export function extractItemsFromResponse<Q extends LibraryQueryType>(
  response: LibraryQueryResponse | Record<string, unknown>,
  queryType: Q
): LibraryItemByQuery[Q][] {
  const extract = EXTRACT_ITEMS[queryType];
  if (!extract) {
    throw new Error(`Unhandled LibraryQueryType: ${String(queryType)}`);
  }
  // The union includes Record<string, unknown>, so this cast is a member extraction.
  return extract(response as Record<string, unknown>);
}

/**
 * Outcome of one page fetch, classified for the hook's callers.
 *
 * `response` is null only when `requireResponse` was false and the server
 * answered with no body (fetchMore's no-op page); executeQuery sets
 * `requireResponse` and treats that same case as an error.
 */
export type PageFetchResult =
  | { kind: 'ok'; response: LibraryQueryResponse | null }
  | { kind: 'stale' }
  | { kind: 'aborted' }
  | { kind: 'error'; error: ApiError };

/**
 * Fetch one page and classify the outcome.
 *
 * The shared core of executeQuery and fetchMore (#5478): the request-id
 * staleness contract (#4609/#4885) and the error classification both used to
 * be duplicated across the two callbacks. Order matters and is preserved:
 * an AbortError wins over staleness (cancellation is not a failure), a
 * superseded request's failure is swallowed (a newer render must not be
 * replaced by a stale error), and only a live request's failure is parsed.
 *
 * `requireResponse` mirrors the two callers' historical difference:
 * executeQuery treated a null response as a QUERY_ERROR, fetchMore as a
 * no-op page.
 *
 * The response is the wire union (#5637); the caller's domain item type comes
 * out of `extractItemsFromResponse`, not from here.
 */
export async function fetchLibraryPage(deps: {
  get: <R>(
    url: string,
    init?: { validate?: (v: unknown) => v is R; signal?: AbortSignal }
  ) => Promise<R | null>;
  url: string;
  validate: (v: unknown) => v is LibraryQueryResponse;
  isStale: () => boolean;
  errorCode: 'QUERY_ERROR' | 'FETCH_MORE_ERROR';
  requireResponse: boolean;
  /** Aborts the HTTP request when a newer query supersedes this one (#5650). */
  signal?: AbortSignal;
}): Promise<PageFetchResult> {
  const { get, url, validate, isStale, errorCode, requireResponse, signal } = deps;

  try {
    const response = await get<LibraryQueryResponse>(url, { validate, signal });

    if (isStale()) {
      // A newer query has taken over — abandon this response entirely rather
      // than rendering results for a term the user has moved past.
      return { kind: 'stale' };
    }

    if (!response && requireResponse) {
      throw new Error('No response from server');
    }

    return { kind: 'ok', response };
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') {
      // Request was cancelled - don't update state
      return { kind: 'aborted' };
    }

    if (isStale()) {
      // Superseded request failed — surfacing its error would replace a
      // newer successful render with a stale failure.
      return { kind: 'stale' };
    }

    return { kind: 'error', error: ApiErrorHandler.parseWithCode(err, errorCode) };
  }
}
