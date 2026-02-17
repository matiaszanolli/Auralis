/**
 * Playlist Management Service (Phase 5a)
 *
 * Provides API functions for playlist operations:
 * - Create/update/delete playlists
 * - Add/remove tracks from playlists
 * - Get playlist details
 *
 * Refactored using Service Factory Pattern (Phase 5a) to reduce code duplication.
 */

import { post, del } from '../utils/apiRequest';
import { ENDPOINTS } from '../config/api';
import { createCrudService } from '../utils/serviceFactory';

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

// Create base CRUD service using factory
const crudService = createCrudService<Playlist, CreatePlaylistRequest>({
  list: ENDPOINTS.PLAYLISTS,
  get: (id) => ENDPOINTS.PLAYLIST(id),
  create: ENDPOINTS.PLAYLISTS,
  update: (id) => ENDPOINTS.PLAYLIST(id),
  delete: (id) => ENDPOINTS.PLAYLIST(id),
});

/**
 * Get all playlists
 */
export async function getPlaylists(): Promise<PlaylistsResponse> {
  const response = await crudService.list();
  const playlistsArray = Array.isArray(response) ? response : (response as any).playlists;
  return { playlists: playlistsArray, total: playlistsArray.length };
}

/**
 * Get playlist by ID with all tracks
 */
export async function getPlaylist(playlistId: number): Promise<Playlist> {
  return crudService.getOne(playlistId);
}

/**
 * Create a new playlist
 */
export async function createPlaylist(request: CreatePlaylistRequest): Promise<Playlist> {
  const data = await crudService.create(request);
  // crudService.create returns Playlist directly
  return (data as any).playlist || data;
}

/**
 * Update playlist name or description
 */
export async function updatePlaylist(
  playlistId: number,
  request: UpdatePlaylistRequest
): Promise<void> {
  await crudService.update(playlistId, request);
}

/**
 * Delete a playlist
 */
export async function deletePlaylist(playlistId: number): Promise<void> {
  await crudService.delete(playlistId);
}

/**
 * Add a single track to playlist
 */
export async function addTrackToPlaylist(
  playlistId: number,
  trackId: number
): Promise<void> {
  await post(ENDPOINTS.ADD_PLAYLIST_TRACK(playlistId), { track_ids: [trackId] });
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
