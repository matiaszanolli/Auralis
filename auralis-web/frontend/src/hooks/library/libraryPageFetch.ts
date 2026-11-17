/**
 * Pure page-fetch helpers for useLibraryPagination.
 *
 * Split out of useLibraryPagination.ts (#5840): the endpoint choice, the
 * guarded GET + transform, and the friendly-error bucketing were spelled out
 * three times (fetchTracks, refreshTracks, loadMore). The hook keeps the
 * state, the abort controllers and the request-id supersession guard.
 *
 * @copyright (C) 2024 Auralis Team
 * @license AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
 */

import { ENDPOINTS, LIBRARY_MAX_PAGE_LIMIT, LIBRARY_PAGE_LIMIT } from '@/config/api';
import { transformTracks, type TrackApiResponse } from '@/api/transformers';
import type { LibraryTrack } from '@/types/domain';
import { get, APIRequestError } from '@/utils/apiRequest';
import { isTracksListShape } from '@/api/responseGuards';

export const PAGE_LIMIT = LIBRARY_PAGE_LIMIT;

interface TracksPageResponse {
  tracks?: TrackApiResponse[];
  has_more?: boolean;
  total?: number;
}

export interface TracksPage {
  tracks: LibraryTrack[];
  hasMore: boolean;
  total: number;
  /** Rows the server returned (before transform), for diagnostics. */
  rawCount: number;
}

export function tracksEndpoint(view: string, offset: number, search = '', limit = PAGE_LIMIT): string {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  // #5866: server-side search (title/artist/album ILIKE) — the client-side
  // filter only ever saw the already-loaded pages, so anything outside them
  // showed as a false "no results" in a large library.
  if (search.trim()) params.set('search', search.trim());
  const path = view === 'favourites'
    ? ENDPOINTS.LIBRARY_TRACKS_FAVORITES
    : ENDPOINTS.LIBRARY_TRACKS;
  return `${path}?${params.toString()}`;
}

/**
 * GET one page through get() with the same isTracksListShape guard
 * useLibraryQuery.ts uses (#5346) — a malformed/renamed `tracks` key throws
 * instead of silently defaulting to an empty list.
 */
export async function fetchTracksPage(
  view: string,
  offset: number,
  signal: AbortSignal,
  search = '',
  limit = PAGE_LIMIT
): Promise<TracksPage> {
  const data = await get<TracksPageResponse>(tracksEndpoint(view, offset, search, limit), {
    signal,
    validate: isTracksListShape,
  });
  return {
    tracks: transformTracks(data.tracks || []),
    hasMore: data.has_more || false,
    total: data.total || 0,
    rawCount: data.tracks?.length || 0,
  };
}

/**
 * statusCode 0 is get()'s marker for a connection-level failure (network or
 * timeout, never reached the server); any other value, including a
 * shape-validation failure, means the server responded but not usefully
 * (#5346).
 */
export function friendlyFetchError(err: unknown, serverFailureMessage: string): string {
  return err instanceof APIRequestError && err.statusCode === 0
    ? 'Failed to connect to server'
    : serverFailureMessage;
}

/**
 * Abort whatever request the ref holds and install a fresh controller (#4891, #5346).
 *
 * Callers keep the returned controller to tell "deliberately aborted (supersession or unmount)"
 * apart from a genuine failure: get() does not preserve the original error's type/name, so abort
 * detection reads the controller's own signal instead.
 */
export function replaceAbortController(ref: { current: AbortController | null }): AbortController {
  ref.current?.abort();
  const controller = new AbortController();
  ref.current = controller;
  return controller;
}

export interface RefreshedPages {
  tracks: TracksPage['tracks'];
  /** Start of the LAST page read - what useLibraryPagination's `offset` means (loadMore adds one
   *  page to it). The first unread page's start would make loadMore skip a whole page. */
  offset: number;
  hasMore: boolean;
  total: number;
}

/**
 * Re-fetch the rows already loaded, so the visible rows are replaced with current data AND
 * pagination continuity is kept (#5626). Requests are as large as the server allows
 * (LIBRARY_MAX_PAGE_LIMIT, in whole pages), so refreshing N loaded pages costs ceil(N / 4)
 * requests instead of N (#5902). Returns null when `isStale()` turned true mid-way.
 * `nextSignal` is called before each request so the caller can supersede the previous one.
 */
export async function fetchLoadedPages(
  view: string,
  search: string,
  loaded: number,
  nextSignal: () => AbortSignal,
  isStale: () => boolean
): Promise<RefreshedPages | null> {
  const pagesPerRequest = Math.floor(LIBRARY_MAX_PAGE_LIMIT / PAGE_LIMIT);
  const tracks: TracksPage['tracks'] = [];
  let rowsRead = 0;
  let hasMore = true;
  let total = 0;
  while (rowsRead < loaded && hasMore) {
    const pagesWanted = Math.min(pagesPerRequest, Math.ceil((loaded - rowsRead) / PAGE_LIMIT));
    const page = await fetchTracksPage(view, rowsRead, nextSignal(), search, pagesWanted * PAGE_LIMIT);
    if (isStale()) return null;
    tracks.push(...page.tracks);
    rowsRead += page.rawCount;
    hasMore = page.hasMore;
    total = page.total;
    if (page.rawCount === 0) break; // an empty page cannot make progress
  }
  // `offset` is the start of the LAST page read (loadMore adds one page to it).
  return { tracks, offset: Math.max(0, Math.ceil(rowsRead / PAGE_LIMIT) - 1) * PAGE_LIMIT, hasMore, total };
}
