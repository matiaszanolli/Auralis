/**
 * Playlist Transformer
 *
 * Transforms backend API playlist data (snake_case) to frontend domain models (camelCase).
 * Fixes #2505: Playlist was the only domain type without a transformer, causing components
 * that follow the camelCase pattern (playlist.trackCount) to always get undefined.
 */

import type { PlaylistApiResponse, PlaylistDetailApiResponse, PlaylistsApiResponse } from './types';
import type { Playlist, PlaylistDetail } from '@/types/domain';
import { transformTrack } from './trackTransformer';

/**
 * Transform a single playlist from API response to domain model
 *
 * Backend contract (snake_case):
 * - track_count (number)
 * - is_smart (boolean)
 * - created_at (string | undefined)
 * - modified_at (string | undefined)
 *
 * Frontend domain (camelCase):
 * - trackCount (number)
 * - isSmart (boolean)
 * - createdAt (string | undefined)
 * - modifiedAt (string | undefined)
 */
export function transformPlaylist(api: PlaylistApiResponse): Playlist {
  return {
    id: api.id,
    name: api.name,
    description: api.description,
    trackCount: api.track_count, // snake → camel
    isSmart: api.is_smart, // snake → camel
    createdAt: api.created_at ?? undefined, // snake → camel, null → undefined
    modifiedAt: api.modified_at ?? undefined, // snake → camel, null → undefined
  };
}

/**
 * Transform a playlist detail response (includes tracks)
 */
export function transformPlaylistDetail(api: PlaylistDetailApiResponse): PlaylistDetail {
  return {
    ...transformPlaylist(api),
    tracks: api.tracks.map(transformTrack),
  };
}

/**
 * Transform an array of playlists from API response
 */
export function transformPlaylists(apiPlaylists: PlaylistApiResponse[]): Playlist[] {
  return apiPlaylists.map(transformPlaylist);
}

/**
 * Transform complete playlists API response (with total count)
 */
export function transformPlaylistsResponse(apiResponse: PlaylistsApiResponse) {
  return {
    playlists: transformPlaylists(apiResponse.playlists),
    total: apiResponse.total,
  };
}
