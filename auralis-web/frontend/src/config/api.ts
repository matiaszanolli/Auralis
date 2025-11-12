/**
 * API Configuration
 *
 * Centralized configuration for API endpoints and base URLs.
 * In development with Vite dev server, use relative URLs to leverage proxy.
 * In production, use absolute URLs.
 */

// Use relative URL in development (Vite proxy handles forwarding)
// Use absolute URL in production build
export const API_BASE_URL = import.meta.env.DEV ? '' : 'http://localhost:8765';

// WebSocket URL - always absolute since WebSocket doesn't use proxy
export const WS_BASE_URL = 'ws://localhost:8765';

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
  PLAYLISTS: '/playlists',
  PLAYLIST: (id: number) => `/playlists/${id}`,
  PLAYLIST_TRACKS: (id: number) => `/playlists/${id}/tracks`,
  ADD_PLAYLIST_TRACK: (id: number) => `/playlists/${id}/tracks`,
  REMOVE_PLAYLIST_TRACK: (id: number, trackId: number) => `/playlists/${id}/tracks/${trackId}`,

  // Queue
  QUEUE: '/player/queue',
  QUEUE_TRACK: (index: number) => `/player/queue/${index}`,
  QUEUE_REORDER: '/player/queue/reorder',
  QUEUE_SHUFFLE: '/player/queue/shuffle',
  QUEUE_CLEAR: '/player/queue/clear',

  // Settings
  SETTINGS: '/settings',
  ENHANCEMENT_SETTINGS: '/settings/enhancement',

  // Library
  LIBRARY_STATS: '/library/stats',
  LIBRARY_TRACKS: '/library/tracks',
  LIBRARY_ALBUMS: '/library/albums',
  LIBRARY_ARTISTS: '/library/artists',

  // Player
  PLAYER_STATUS: '/player/status',
  PLAYER_LOAD: '/player/load',
  PLAYER_PLAY: '/player/play',
  PLAYER_PAUSE: '/player/pause',
  PLAYER_STOP: '/player/stop',
  PLAYER_SEEK: '/player/seek',
  PLAYER_VOLUME: '/player/volume',
} as const;
