/**
 * API Configuration
 *
 * Centralized configuration for API endpoints and base URLs.
 * In development with Vite dev server, use relative URLs to leverage proxy.
 * In production, use absolute URLs.
 */

// Use relative URL in development (Vite proxy handles forwarding)
// Use absolute URL in production build.
//
// VITE_API_URL / VITE_WS_URL override both (#4468). Without an escape hatch
// there was no way to move off port 8765 when it is already taken, and this
// module disagreed with the retired services/api client (now cacheShapeGuards.ts), which always
// read `import.meta.env.VITE_API_URL ?? API_BASE_URL`. Same `??` semantics as
// that client: only an undefined override falls through to the default, so an
// explicit empty string still selects the dev-style relative URL.
export const API_BASE_URL = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? '' : 'http://localhost:8765');

// WebSocket URL - always absolute since WebSocket doesn't use proxy
export const WS_BASE_URL = import.meta.env.VITE_WS_URL ?? 'ws://localhost:8765';

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
