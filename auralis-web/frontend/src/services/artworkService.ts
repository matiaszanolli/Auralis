/**
 * Artwork Service (Phase 5a)
 * ~~~~~~~~~~~~~~~~
 *
 * Service for managing album artwork: extraction, download, and deletion.
 *
 * Refactored using Service Factory Pattern (Phase 5a) to reduce code duplication.
 */

import { API_BASE_URL } from '@/config/api';
import { createCrudService } from '@/utils/serviceFactory';

export interface ArtworkResponse {
  message: string;
  artwork_url: string;
  album_id: number;
  artist?: string;
  album?: string;
}

export interface ArtworkRequest {
  // Empty request body for artwork operations
}

type ArtworkParams = { albumId: number } & Record<string, unknown>;

// Create base CRUD service using factory with custom endpoints
const crudService = createCrudService<ArtworkResponse, ArtworkRequest, number, ArtworkParams>({
  custom: {
    extract: (data) => `/api/albums/${data?.albumId}/artwork/extract`,
    download: (data) => `/api/albums/${data?.albumId}/artwork/download`,
    delete: (data) => `/api/albums/${data?.albumId}/artwork`,
  },
});

/**
 * Extract artwork from album's audio files
 */
export async function extractArtwork(albumId: number): Promise<ArtworkResponse> {
  return crudService.custom<ArtworkResponse>('extract', 'post', { albumId });
}

/**
 * Download artwork from online sources (MusicBrainz, iTunes)
 */
export async function downloadArtwork(albumId: number): Promise<ArtworkResponse> {
  return crudService.custom<ArtworkResponse>('download', 'post', { albumId });
}

/**
 * Delete album artwork
 */
export async function deleteArtwork(albumId: number): Promise<{ message: string; album_id: number }> {
  return crudService.custom<{ message: string; album_id: number }>('delete', 'delete', { albumId });
}

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
  // Only append to the album-artwork endpoint (which understands `size`); leave
  // data URIs / external URLs / already-sized URLs untouched.
  if (!url || !size || size <= 0) return url;
  if (!url.includes('/artwork') || /[?&]size=/.test(url)) return url;
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}size=${Math.round(size)}`;
}
