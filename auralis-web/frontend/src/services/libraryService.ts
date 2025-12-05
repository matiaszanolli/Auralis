/**
 * Library Service
 *
 * Provides API functions for library operations:
 * - Fetch artist tracks for playback
 * - Library browsing and search
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { ENDPOINTS, getApiUrl } from '../config/api';

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
 * @param artistId - The ID of the artist
 * @returns Promise resolving to artist tracks response
 */
export async function getArtistTracks(artistId: number): Promise<ArtistTracksResponse> {
  const url = getApiUrl(ENDPOINTS.ARTIST_TRACKS(artistId));
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Failed to fetch artist tracks: ${response.statusText}`);
  }

  return response.json();
}

export default {
  getArtistTracks,
};
