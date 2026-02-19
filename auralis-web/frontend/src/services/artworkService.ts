/**
 * Artwork Service (Phase 5a)
 * ~~~~~~~~~~~~~~~~
 *
 * Service for managing album artwork: extraction, download, and deletion.
 *
 * Refactored using Service Factory Pattern (Phase 5a) to reduce code duplication.
 */

import { API_BASE_URL } from '../config/api';
import { createCrudService } from '../utils/serviceFactory';

export interface ArtworkResponse {
  message: string;
  artwork_path: string;
  album_id: number;
  artist?: string;
  album?: string;
}

export interface ArtworkRequest {
  // Empty request body for artwork operations
}

// Create base CRUD service using factory with custom endpoints
const crudService = createCrudService<ArtworkResponse, ArtworkRequest>({
  custom: {
    extract: (data: { albumId: number }) => `/api/albums/${data.albumId}/artwork/extract`,
    download: (data: { albumId: number }) => `/api/albums/${data.albumId}/artwork/download`,
    delete: (data: { albumId: number }) => `/api/albums/${data.albumId}/artwork`,
  },
});

/**
 * Extract artwork from album's audio files
 */
export async function extractArtwork(albumId: number): Promise<ArtworkResponse> {
  return crudService.custom('extract', 'post', { albumId });
}

/**
 * Download artwork from online sources (MusicBrainz, iTunes)
 */
export async function downloadArtwork(albumId: number): Promise<ArtworkResponse> {
  return crudService.custom('download', 'post', { albumId });
}

/**
 * Delete album artwork
 */
export async function deleteArtwork(albumId: number): Promise<{ message: string; album_id: number }> {
  return crudService.custom('delete', 'delete', { albumId });
}

/**
 * Get artwork URL for an album
 */
export function getArtworkUrl(albumId: number): string {
  return `${API_BASE_URL}/api/albums/${albumId}/artwork`;
}
