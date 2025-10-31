/**
 * Playlist Management Service
 *
 * Provides API functions for playlist operations:
 * - Create/update/delete playlists
 * - Add/remove tracks from playlists
 * - Get playlist details
 */

const API_BASE = '/api';

export interface Playlist {
  id: number;
  name: string;
  description: string;
  is_smart: boolean;
  smart_criteria: string | null;
  auto_master_enabled: boolean;
  mastering_profile: string;
  normalize_levels: boolean;
  track_count: number;
  total_duration: number;
  created_at: string;
  updated_at: string;
  tracks?: Track[];
}

export interface Track {
  id: number;
  title: string;
  artist?: string;
  album?: string;
  duration: number;
  filepath: string;
}

export interface PlaylistsResponse {
  playlists: Playlist[];
  total: number;
}

export interface CreatePlaylistRequest {
  name: string;
  description?: string;
  track_ids?: number[];
}

export interface UpdatePlaylistRequest {
  name?: string;
  description?: string;
}

/**
 * Get all playlists
 */
export async function getPlaylists(): Promise<PlaylistsResponse> {
  const response = await fetch(`${API_BASE}/playlists`);

  if (!response.ok) {
    throw new Error(`Failed to get playlists: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get playlist by ID with all tracks
 */
export async function getPlaylist(playlistId: number): Promise<Playlist> {
  const response = await fetch(`${API_BASE}/playlists/${playlistId}`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to get playlist');
  }

  return response.json();
}

/**
 * Create a new playlist
 */
export async function createPlaylist(request: CreatePlaylistRequest): Promise<Playlist> {
  const response = await fetch(`${API_BASE}/playlists`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to create playlist');
  }

  const data = await response.json();
  return data.playlist;
}

/**
 * Update playlist name or description
 */
export async function updatePlaylist(
  playlistId: number,
  request: UpdatePlaylistRequest
): Promise<void> {
  const response = await fetch(`${API_BASE}/playlists/${playlistId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to update playlist');
  }
}

/**
 * Delete a playlist
 */
export async function deletePlaylist(playlistId: number): Promise<void> {
  const response = await fetch(`${API_BASE}/playlists/${playlistId}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to delete playlist');
  }
}

/**
 * Add a single track to playlist
 */
export async function addTrackToPlaylist(
  playlistId: number,
  trackId: number
): Promise<void> {
  const response = await fetch(`${API_BASE}/playlists/${playlistId}/tracks`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ track_id: trackId }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to add track to playlist');
  }
}

/**
 * Add multiple tracks to playlist
 */
export async function addTracksToPlaylist(
  playlistId: number,
  trackIds: number[]
): Promise<number> {
  const response = await fetch(`${API_BASE}/playlists/${playlistId}/tracks`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ track_ids: trackIds }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to add tracks to playlist');
  }

  const data = await response.json();
  return data.added_count;
}

/**
 * Remove a track from playlist
 */
export async function removeTrackFromPlaylist(
  playlistId: number,
  trackId: number
): Promise<void> {
  const response = await fetch(`${API_BASE}/playlists/${playlistId}/tracks/${trackId}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to remove track from playlist');
  }
}

/**
 * Clear all tracks from playlist
 */
export async function clearPlaylist(playlistId: number): Promise<void> {
  const response = await fetch(`${API_BASE}/playlists/${playlistId}/tracks`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to clear playlist');
  }
}

export default {
  getPlaylists,
  getPlaylist,
  createPlaylist,
  updatePlaylist,
  deletePlaylist,
  addTrackToPlaylist,
  addTracksToPlaylist,
  removeTrackFromPlaylist,
  clearPlaylist,
};
