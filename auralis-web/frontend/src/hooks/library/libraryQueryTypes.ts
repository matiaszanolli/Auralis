/**
 * Shared types and pure helpers for the useLibraryQuery hook family.
 *
 * Split out of useLibraryQuery.ts (#5478, continuing #5043's extraction) so
 * the hook file holds only hook logic. Everything here is framework-free.
 *
 * @module hooks/library/libraryQueryTypes
 */

import type { ApiError } from '@/types/api';
import type { AlbumsApiResponse, ArtistsApiResponse, TracksApiResponse } from '@/api/transformers';
import { isAlbumsListShape, isArtistsListShape, isTracksListShape } from '@/api/responseGuards';

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
 * Wire shape of one paginated library page (#5637): the backend's canonical
 * `{ tracks | albums | artists: [...], total, offset, limit, has_more }`.
 * Which member arrives is chosen by the query type at runtime (see
 * QUERY_TYPE_ENDPOINT); the matching QUERY_TYPE_GUARD entry is the runtime
 * half of that association, and the items are the post-transform domain
 * `T` only after `extractItemsFromResponse` runs. This replaces the old
 * `LibraryQueryResponse<T>`, which declared `items`/`hasMore` fields that
 * never existed on the wire — any consumer trusting them read `undefined`.
 */
export type LibraryQueryResponse = TracksApiResponse | AlbumsApiResponse | ArtistsApiResponse;

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
 * Runtime shape guard per query type (#5026) — covers every consumer of
 * *this* hook (useLibraryQuery, useTracksQuery, useAlbumsQuery,
 * useArtistsQuery, useInfiniteScroll) at once, since these three list
 * responses are its only fetch call sites. It is NOT the only place tracks
 * are fetched, though: the main library track list is fed by the separate
 * useLibraryPagination.ts stack, which has (since #5346) its own
 * isTracksListShape guard on both of its call sites. Guard coverage here is
 * opt-in per hook, not automatic for every consumer of `/api/library/tracks`.
 * See `@/api/responseGuards` for what each guard checks.
 */
export const QUERY_TYPE_GUARD: Record<LibraryQueryType, (v: unknown) => v is LibraryQueryResponse> = {
  tracks: isTracksListShape,
  albums: isAlbumsListShape,
  artists: isArtistsListShape,
};

/**
 * Derive `hasMore` from a page response, preferring the backend `has_more`
 * contract — the same one useLibraryPagination uses — so the two track
 * pagination stacks no longer disagree (#4422 / F2-01). Falls back to a cursor
 * comparison only when the backend omits the flag.
 *
 * The argument is the two fields this function actually reads, so every wire
 * shape (and a plain record, for tests) is callable without a cast (#5637).
 */
export function deriveHasMore(
  response: { has_more?: unknown; hasMore?: unknown; total?: unknown },
  pageOffset: number,
  pageLength: number
): boolean {
  const backend = response.has_more ?? response.hasMore;
  if (typeof backend === 'boolean') return backend;
  const total = typeof response.total === 'number' ? response.total : 0;
  return pageOffset + pageLength < total;
}
