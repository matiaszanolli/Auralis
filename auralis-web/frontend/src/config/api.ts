/**
 * API Configuration
 *
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
