/**
 * Library Service
 *
 * Provides API functions for library operations:
 * - Fetch artist tracks for playback
 * - Library browsing and search
 *
 * Refactored to use centralized apiRequest utility for consistent error handling
 * and reduced code duplication (eliminates raw fetch wrapper pattern).
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { get } from '../utils/apiRequest';
import { ENDPOINTS } from '../config/api';

export interface TrackInArtist {
  id: number;
  title: string;
  album: string;
  album_id: number;
  duration: number;
  track_number?: number;
  disc_number?: number;
}

export interface ArtistTracksResponse {
  artist_id: number;
  artist_name: string;
  tracks: TrackInArtist[];
  total_tracks: number;
}

/**
 * Fetch all tracks for a specific artist
 *
 * @param artistId - The ID of the artist
 * @returns Promise resolving to artist tracks response
 * @throws APIRequestError on network or API errors
 *
 * @example
 * const { tracks, artist_name } = await getArtistTracks(42);
 */
export async function getArtistTracks(artistId: number): Promise<ArtistTracksResponse> {
  return get<ArtistTracksResponse>(ENDPOINTS.ARTIST_TRACKS(artistId));
}

export default {
  getArtistTracks,
};
