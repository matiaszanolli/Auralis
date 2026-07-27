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

import { post, del } from '@/utils/apiRequest';
import { ENDPOINTS } from '@/config/api';
import { createCrudService } from '@/utils/serviceFactory';
import { isPlaylistShape, isPlaylistsListShape } from '@/api/responseGuards';

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

import type { Track } from '@/types/domain';

export interface PlaylistsResponse {
  playlists: Playlist[];
  /** Total number of playlists on the server, not the length of this page. */
  total: number;
  offset?: number;
  limit?: number;
  has_more?: boolean;
}

/**
 * Maximum page size accepted by `GET /api/playlists` (#4554).
 *
 * The endpoint is paginated and defaults to 50 server-side. Every current
 * caller — the add-to-playlist menus and the playlist view — wants the whole
 * collection, so the service asks for the cap rather than inheriting a default
 * that would silently truncate the list for anyone with more than 50
 * playlists. `has_more` on the response says whether that was enough.
 */
export const PLAYLISTS_PAGE_LIMIT = 200;

export interface PlaylistListParams extends Record<string, unknown> {
  limit?: number;
  offset?: number;
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
const crudService = createCrudService<Playlist, CreatePlaylistRequest, number, PlaylistListParams>({
  list: (params) => {
    const search = new URLSearchParams({
      limit: String(params?.limit ?? PLAYLISTS_PAGE_LIMIT),
      offset: String(params?.offset ?? 0),
    });
    return `${ENDPOINTS.PLAYLISTS}?${search.toString()}`;
  },
  get: (id) => ENDPOINTS.PLAYLIST(id),
  // Runtime shape checks at the boundary (#4607).
  guards: { list: isPlaylistsListShape, get: isPlaylistShape },
  create: ENDPOINTS.PLAYLISTS,
  update: (id) => ENDPOINTS.PLAYLIST(id),
  delete: (id) => ENDPOINTS.PLAYLIST(id),
});

/**
 * Get a page of playlists (defaults to the maximum page size, see
 * PLAYLISTS_PAGE_LIMIT).
 */
export async function getPlaylists(params?: PlaylistListParams): Promise<PlaylistsResponse> {
  const response = await crudService.list(params);
  // Runtime shape validation — response may be a bare array or {playlists: [...]}
  const envelope = (!Array.isArray(response) && response && typeof response === 'object')
    ? response as unknown as PlaylistsResponse
    : null;
  const playlistsArray = Array.isArray(response)
    ? response
    : (envelope && Array.isArray(envelope.playlists))
      ? envelope.playlists
      : [];

  // Prefer the server's COUNT — with pagination the page length is no longer
  // the collection size (#4554). Fall back to the page length only when the
  // response is a bare array (older backend) or omits `total`.
  const total = typeof envelope?.total === 'number' ? envelope.total : playlistsArray.length;

  return {
    playlists: playlistsArray,
    total,
    offset: envelope?.offset,
    limit: envelope?.limit,
    has_more: envelope?.has_more,
  };
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
  // Response may be {playlist: {...}} or a bare Playlist object
  if (data && typeof data === 'object' && 'playlist' in data) {
    return (data as { playlist: Playlist }).playlist;
  }
  return data;
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
  const data = await post<{ added_count: number }>(
    ENDPOINTS.ADD_PLAYLIST_TRACK(playlistId),
    { track_ids: trackIds }
  );
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
