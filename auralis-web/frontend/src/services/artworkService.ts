/**
 * Artwork Service
 * ~~~~~~~~~~~~~~~~
 *
 * Service for managing album artwork: extraction, download, and deletion.
 */

const API_BASE = 'http://localhost:8765';

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
  const response = await fetch(`${API_BASE}/api/albums/${albumId}/artwork/extract`, {
    method: 'POST',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to extract artwork');
  }

  return response.json();
}

/**
 * Download artwork from online sources (MusicBrainz, iTunes)
 */
export async function downloadArtwork(albumId: number): Promise<ArtworkResponse> {
  const response = await fetch(`${API_BASE}/api/albums/${albumId}/artwork/download`, {
    method: 'POST',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to download artwork');
  }

  return response.json();
}

/**
 * Delete album artwork
 */
export async function deleteArtwork(albumId: number): Promise<{ message: string; album_id: number }> {
  const response = await fetch(`${API_BASE}/api/albums/${albumId}/artwork`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to delete artwork');
  }

  return response.json();
}

/**
 * Get artwork URL for an album
 */
export function getArtworkUrl(albumId: number): string {
  return `${API_BASE}/api/albums/${albumId}/artwork?t=${Date.now()}`;
}
