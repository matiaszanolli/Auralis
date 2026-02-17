/**
 * Artist Transformer
 *
 * Transforms backend API artist data (snake_case) to frontend domain models (camelCase).
 */

import type { ArtistApiResponse, ArtistsApiResponse } from './types';
import type { Artist } from '@/types/domain';

/**
 * Transform a single artist from API response to domain model
 *
 * Backend contract (snake_case):
 * - artwork_url (string | null)  — issue #2110: was incorrectly artwork_path
 * - track_count (number)
 * - album_count (number)
 * - date_added (string | undefined)
 *
 * Frontend domain (camelCase):
 * - artworkUrl (string | undefined)
 * - trackCount (number)
 * - albumCount (number)
 * - dateAdded (string | undefined)
 */
export function transformArtist(apiArtist: ArtistApiResponse): Artist {
  return {
    id: apiArtist.id,
    name: apiArtist.name,
    artworkUrl: apiArtist.artwork_url ?? undefined, // snake → camel, null → undefined
    trackCount: apiArtist.track_count, // snake → camel
    albumCount: apiArtist.album_count, // snake → camel
    dateAdded: apiArtist.date_added ?? undefined, // snake → camel, null → undefined
  };
}

/**
 * Transform an array of artists from API response
 */
export function transformArtists(apiArtists: ArtistApiResponse[]): Artist[] {
  return apiArtists.map(transformArtist);
}

/**
 * Transform complete artists API response (with pagination)
 */
export function transformArtistsResponse(apiResponse: ArtistsApiResponse) {
  return {
    artists: transformArtists(apiResponse.artists),
    total: apiResponse.total,
    offset: apiResponse.offset,
    limit: apiResponse.limit,
    hasMore: apiResponse.has_more, // snake → camel
  };
}
