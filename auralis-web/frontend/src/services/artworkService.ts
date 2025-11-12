/**
 * Artwork Service
 * ~~~~~~~~~~~~~~~~
 *
 * Service for managing album artwork: extraction, download, and deletion.
 */

import { post, del } from '../utils/apiRequest';
import { API_BASE_URL } from '../config/api';

export interface ArtworkResponse {
  message: string;
  artwork_path: string;
  album_id: number;
  artist?: string;
  album?: string;
}

/**
 * Extract artwork from album's audio files
 */
export async function extractArtwork(albumId: number): Promise<ArtworkResponse> {
  return post(`/albums/${albumId}/artwork/extract`, {});
}

/**
 * Download artwork from online sources (MusicBrainz, iTunes)
 */
export async function downloadArtwork(albumId: number): Promise<ArtworkResponse> {
  return post(`/albums/${albumId}/artwork/download`, {});
}

/**
 * Delete album artwork
 */
export async function deleteArtwork(albumId: number): Promise<{ message: string; album_id: number }> {
  return del(`/albums/${albumId}/artwork`);
}

/**
 * Get artwork URL for an album
 */
export function getArtworkUrl(albumId: number): string {
  return `${API_BASE_URL}/api/albums/${albumId}/artwork?t=${Date.now()}`;
}
