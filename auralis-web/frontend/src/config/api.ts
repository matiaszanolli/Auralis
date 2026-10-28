/**
 * API Configuration
 *
 * Centralized configuration for API endpoints and base URLs.
 *
 * A production bundle is served by the backend itself, so the page's own
 * origin IS the backend, on whatever port `launch-auralis-web.py --port N`
 * bound (#5886). Only the Vite dev server (`import.meta.env.DEV`) runs on a
 * different port from the backend: REST goes through its proxy (relative URLs)
 * and the WebSocket connects straight to :8765, since Vite's WS proxy is
 * unreliable. The production fallback used to be a hard-coded :8765 as well,
 * and the WS URL was picked by "localhost and port >= 3000", which a
 * production page on :9000 also matched.
 *
 * VITE_API_URL / VITE_WS_URL override both (#4468); an absolute VITE_API_URL alone also
 * moves the WebSocket (#5654), and VITE_WS_URL still wins. Same `??` semantics as the
 * retired services/api client (now cacheShapeGuards.ts): only an undefined
 * override falls through to the default, so an explicit empty string still
 * selects the relative URL.
 */

/** Same-origin WebSocket base for a page the backend served. */
export function sameOriginWsBase(location: Pick<Location, 'protocol' | 'host'>): string {
  return `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}`;
}

/**
 * The WebSocket base of an absolute `VITE_API_URL` (`http://h:9` -> `ws://h:9`), so moving
 * the backend with one variable moves both transports (#5654). Undefined for a relative
 * or empty value, which names no host to derive from.
 */
export function wsBaseFromApiBase(apiBase: string | undefined): string | undefined {
  if (!apiBase || !/^https?:\/\//.test(apiBase)) return undefined;
  return apiBase.replace(/^http/, 'ws').replace(/\/+$/, '');
}

// Relative in both modes: the Vite proxy in dev, the backend's own origin in production.
export const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';

export const WS_BASE_URL =
  import.meta.env.VITE_WS_URL ??
  wsBaseFromApiBase(import.meta.env.VITE_API_URL) ??
  (import.meta.env.DEV ? 'ws://localhost:8765' : sameOriginWsBase(window.location));

/**
 * Upper bound for a library-scan request, in ms — deliberately NOT the shared
 * 30s `DEFAULT_TIMEOUT_MS`.
 *
 * A real library scan runs for minutes, and since #4820 the backend treats an
 * aborted fetch as "stop the scan": under the shared default, every scan longer
 * than 30 seconds would abort its own fetch and take the running scan down with
 * it. The meaningful bound is the backend's own `AURALIS_SCAN_TIMEOUT` (1h),
 * which answers 504 rather than hanging, so this sits just past it — the request
 * stays bounded (#5019's point) without being the thing that gives up first.
 *
 * Every caller of POST `ENDPOINTS.LIBRARY_SCAN` must pass this (#5643).
 */
export const SCAN_TIMEOUT_MS = 3_660_000;

/**
 * Get full API URL for an endpoint
 */
export function getApiUrl(path: string): string {
  // Ensure path starts with /
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
}

/**
 * Common API endpoints
 * Use these constants instead of hardcoding endpoint strings
 */
export const ENDPOINTS = {
  // Playlists
  PLAYLISTS: '/api/playlists',
  PLAYLIST: (id: number) => `/api/playlists/${id}`,
  PLAYLIST_TRACKS: (id: number) => `/api/playlists/${id}/tracks`,
  ADD_PLAYLIST_TRACK: (id: number) => `/api/playlists/${id}/tracks`,
  REMOVE_PLAYLIST_TRACK: (id: number, trackId: number) => `/api/playlists/${id}/tracks/${trackId}`,

  // Queue
  QUEUE: '/api/player/queue',
  QUEUE_ADD_TRACK: '/api/player/queue/add-track',
  QUEUE_ADD_TRACKS: '/api/player/queue/add-tracks',

  // Settings
  SETTINGS: '/api/settings',

  // Library
  LIBRARY_STATS: '/api/library/stats',
  LIBRARY_TRACKS: '/api/library/tracks',
  LIBRARY_TRACKS_FAVORITES: '/api/library/tracks/favorites',
  LIBRARY_ALBUMS: '/api/albums',
  LIBRARY_ARTISTS: '/api/artists',
  ARTIST_TRACKS: (artistId: number) => `/api/artists/${artistId}/tracks`,
  TRACK_FAVORITE: (trackId: number) => `/api/library/tracks/${trackId}/favorite`,

  // Enhancement
  ENHANCEMENT_TOGGLE: '/api/player/enhancement/toggle',
  ENHANCEMENT_PRESET: '/api/player/enhancement/preset',
  ENHANCEMENT_INTENSITY: '/api/player/enhancement/intensity',

  // Library scan
  LIBRARY_SCAN: '/api/library/scan',
  LIBRARY_RESET: '/api/library/reset',

  // Player
  PLAYER_STATUS: '/api/player/status',
  PLAYER_LOAD: '/api/player/load',
  PLAYER_NEXT: '/api/player/next',
  PLAYER_PREVIOUS: '/api/player/previous',
  PLAYER_SEEK: '/api/player/seek',
  PLAYER_VOLUME: '/api/player/volume',
} as const;

/**
 * Library list page size (#6217): the default `limit` every library query
 * path uses — was hand-typed in six places (libraryPageFetch,
 * libraryQueryRequest, useInfiniteAlbums x2, useLibraryQuery, playlistService
 * has its own PLAYLISTS_PAGE_LIMIT for a different endpoint).
 */
export const LIBRARY_PAGE_LIMIT = 50;
