/**
 * Artwork Service (Phase 5a)
 * ~~~~~~~~~~~~~~~~
 *
 * Builds album-artwork URLs, including the downscaled-thumbnail variants the
 * backend serves from cache buckets (#4447).
 */

import { API_BASE_URL } from '@/config/api';

// #5214: extractArtwork / downloadArtwork / deleteArtwork were deleted, along
// with the ArtworkResponse/ArtworkRequest types and the createCrudService()
// wiring that existed only to back them. All three had tests but no caller —
// no component or hook ever invoked them, so the artwork-management UI they
// were built for was never wired up. The backend endpoints
// (/api/albums/{id}/artwork/{extract,download} and DELETE) are untouched, so
// re-adding a three-line wrapper is trivial if that UI is ever built.
//
// What remains here are the two URL builders, which do have real callers.

export interface ArtworkUrlOptions {
  /**
   * Max dimension (px) hint for a downscaled thumbnail. The backend snaps this
   * up to a cache bucket and serves a size-appropriate image, so small
   * thumbnails don't force the browser to decode/hold full-resolution bitmaps
   * (#4447). Omit for full resolution (e.g. a detail hero).
   */
  size?: number;
  /** Cache-busting revision (from artwork_updated WS messages, #2867). */
  revision?: number;
}

/**
 * Get the artwork URL for an album, optionally requesting a downscaled variant.
 */
export function getArtworkUrl(albumId: number, options: ArtworkUrlOptions = {}): string {
  const params = new URLSearchParams();
  if (options.size && options.size > 0) params.set('size', String(Math.round(options.size)));
  if (options.revision && options.revision > 0) params.set('v', String(options.revision));
  const query = params.toString();
  return `${API_BASE_URL}/api/albums/${albumId}/artwork${query ? `?${query}` : ''}`;
}

/**
 * Append a thumbnail `size` hint to an already-built artwork URL (e.g. a
 * backend-provided `track.artworkUrl`). No-op for empty/undefined URLs (#4447).
 */
export function withArtworkSize(url: string | undefined, size: number): string | undefined {
  // Only append to OUR artwork endpoints, which understand `size`. Leave data
  // URIs, already-sized URLs, and any absolute URL untouched.
  //
  // The guard used to be a bare `url.includes('/artwork')` (#4526). That held
  // only by luck: artist artwork is an external CDN URL rendered directly (the
  // one artwork field that is deliberately NOT rewritten to an /api path), and
  // any such URL containing the substring `/artwork` — a Discogs or Wikimedia
  // path segment is enough — would have had `?size=N` appended and been sent to
  // a third-party host that does not understand it. Requiring the `/api/`
  // prefix makes same-origin the actual condition rather than a coincidence.
  if (!url || !size || size <= 0) return url;
  if (!url.startsWith('/api/')) return url;
  if (!url.includes('/artwork') || /[?&]size=/.test(url)) return url;
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}size=${Math.round(size)}`;
}
