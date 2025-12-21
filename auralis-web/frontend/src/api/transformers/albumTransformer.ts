/**
 * Album Transformer
 *
 * Transforms backend API album data (snake_case) to frontend domain models (camelCase).
 * This is the single source of truth for album data transformation.
 */

import type { AlbumApiResponse, AlbumsApiResponse } from './types';
import type { Album } from '@/types/domain';

/**
 * Transform a single album from API response to domain model
 *
 * Backend contract (snake_case):
 * - artwork_path (string | null)
 * - track_count (number)
 * - total_duration (number)
 *
 * Frontend domain (camelCase):
 * - artworkUrl (string | undefined)
 * - trackCount (number)
 * - totalDuration (number)
 */
export function transformAlbum(apiAlbum: AlbumApiResponse): Album {
  return {
    id: apiAlbum.id,
    title: apiAlbum.title,
    artist: apiAlbum.artist,
    year: apiAlbum.year ?? undefined,
    artworkUrl: apiAlbum.artwork_path ?? undefined, // snake → camel, null → undefined
    trackCount: apiAlbum.track_count, // snake → camel
    totalDuration: apiAlbum.total_duration, // snake → camel
  };
}

/**
 * Transform an array of albums from API response
 */
export function transformAlbums(apiAlbums: AlbumApiResponse[]): Album[] {
  return apiAlbums.map(transformAlbum);
}

/**
 * Transform complete albums API response (with pagination)
 */
export function transformAlbumsResponse(apiResponse: AlbumsApiResponse) {
  return {
    albums: transformAlbums(apiResponse.albums),
    total: apiResponse.total,
    offset: apiResponse.offset,
    limit: apiResponse.limit,
    hasMore: apiResponse.has_more, // snake → camel
  };
}
