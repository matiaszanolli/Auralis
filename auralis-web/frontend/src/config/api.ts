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
// module disagreed with services/api/standardizedAPIClient.ts, which has always
// read `import.meta.env.VITE_API_URL ?? API_BASE_URL`. Same `??` semantics as
// that client: only an undefined override falls through to the default, so an
// explicit empty string still selects the dev-style relative URL.
export const API_BASE_URL = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? '' : 'http://localhost:8765');

// WebSocket URL - always absolute since WebSocket doesn't use proxy
export const WS_BASE_URL = import.meta.env.VITE_WS_URL ?? 'ws://localhost:8765';

/**
 * Get full API URL for an endpoint
 */
export function getApiUrl(path: string): string {
  // Ensure path starts with /
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
}

/**
 * Get WebSocket URL
 */
export function getWsUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${WS_BASE_URL}${normalizedPath}`;
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
  QUEUE_TRACK: (index: number) => `/api/player/queue/${index}`,
  QUEUE_ADD_TRACK: '/api/player/queue/add-track',
  QUEUE_REORDER: '/api/player/queue/reorder',
  QUEUE_SHUFFLE: '/api/player/queue/shuffle',
  QUEUE_CLEAR: '/api/player/queue/clear',

  // Settings
  SETTINGS: '/api/settings',
  ENHANCEMENT_SETTINGS: '/api/settings/enhancement',

  // Library
  LIBRARY_STATS: '/api/library/stats',
  LIBRARY_TRACKS: '/api/library/tracks',
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
  PLAYER_PLAY: '/api/player/play',
  PLAYER_PAUSE: '/api/player/pause',
  PLAYER_STOP: '/api/player/stop',
  PLAYER_NEXT: '/api/player/next',
  PLAYER_PREVIOUS: '/api/player/previous',
  PLAYER_SEEK: '/api/player/seek',
  PLAYER_VOLUME: '/api/player/volume',
} as const;
