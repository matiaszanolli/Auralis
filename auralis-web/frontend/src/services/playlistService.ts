/**
 * Playlist Management Service
 *
 * Provides API functions for playlist operations:
 * - Create/update/delete playlists
 * - Add/remove tracks from playlists
 * - Get playlist details
 */

import { get, post, put, del } from '../utils/apiRequest';
import { ENDPOINTS } from '../config/api';

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
  return get(ENDPOINTS.PLAYLISTS);
}

/**
 * Get playlist by ID with all tracks
 */
export async function getPlaylist(playlistId: number): Promise<Playlist> {
  return get(ENDPOINTS.PLAYLIST(playlistId));
}

/**
 * Create a new playlist
 */
export async function createPlaylist(request: CreatePlaylistRequest): Promise<Playlist> {
  const data = await post(ENDPOINTS.PLAYLISTS, request);
  return data.playlist;
}

/**
 * Update playlist name or description
 */
export async function updatePlaylist(
  playlistId: number,
  request: UpdatePlaylistRequest
): Promise<void> {
  await put(ENDPOINTS.PLAYLIST(playlistId), request);
}

/**
 * Delete a playlist
 */
export async function deletePlaylist(playlistId: number): Promise<void> {
  await del(ENDPOINTS.PLAYLIST(playlistId));
}

/**
 * Add a single track to playlist
 */
export async function addTrackToPlaylist(
  playlistId: number,
  trackId: number
): Promise<void> {
  await post(ENDPOINTS.ADD_PLAYLIST_TRACK(playlistId), { track_id: trackId });
}

/**
 * Add multiple tracks to playlist
 */
export async function addTracksToPlaylist(
  playlistId: number,
  trackIds: number[]
): Promise<number> {
  const data = await post(ENDPOINTS.ADD_PLAYLIST_TRACK(playlistId), { track_ids: trackIds });
  return data.added_count;
}

/**
 * Remove a track from playlist
 */
export async function removeTrackFromPlaylist(
  playlistId: number,
  trackId: number
): Promise<void> {
  await del(ENDPOINTS.REMOVE_PLAYLIST_TRACK(playlistId, trackId));
}

/**
 * Clear all tracks from playlist
 */
export async function clearPlaylist(playlistId: number): Promise<void> {
  await del(ENDPOINTS.PLAYLIST_TRACKS(playlistId));
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
