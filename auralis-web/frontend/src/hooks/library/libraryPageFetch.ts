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

import { transformTracks, type TrackApiResponse } from '@/api/transformers';
import type { LibraryTrack } from '@/types/domain';
import { get, APIRequestError } from '@/utils/apiRequest';
import { isTracksListShape } from '@/api/responseGuards';

export const PAGE_LIMIT = 50;

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

export function tracksEndpoint(view: string, offset: number): string {
  return view === 'favourites'
    ? `/api/library/tracks/favorites?limit=${PAGE_LIMIT}&offset=${offset}`
    : `/api/library/tracks?limit=${PAGE_LIMIT}&offset=${offset}`;
}

/**
 * GET one page through get() with the same isTracksListShape guard
 * useLibraryQuery.ts uses (#5346) — a malformed/renamed `tracks` key throws
 * instead of silently defaulting to an empty list.
 */
export async function fetchTracksPage(
  view: string,
  offset: number,
  signal: AbortSignal
): Promise<TracksPage> {
  const data = await get<TracksPageResponse>(tracksEndpoint(view, offset), {
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
