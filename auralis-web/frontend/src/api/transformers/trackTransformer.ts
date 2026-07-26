/**
 * Track Transformer
 *
 * Transforms backend API track data (snake_case) to frontend domain models (camelCase).
 */

import type { TrackApiResponse, TracksApiResponse } from './types';
import type { Track } from '@/types/domain';

/**
 * Transform a single track from API response to domain model
 *
 * Backend contract (snake_case):
 * - sample_rate, bit_depth, crest_factor, date_added, date_modified
 *
 * Frontend domain (camelCase):
 * - sampleRate, bitDepth, crestFactor, dateAdded, dateModified
 */
export function transformTrack(apiTrack: TrackApiResponse): Track {
  // Backend sends artists/genres as arrays; fall back to singular fields if present.
  // Fixes #2263: previously read apiTrack.artist which was always undefined.
  const artist = apiTrack.artists?.[0] ?? apiTrack.artist ?? '';
  const genre = apiTrack.genres?.[0] ?? apiTrack.genre;

  return {
    id: apiTrack.id,
    title: apiTrack.title,
    artist,
    album: apiTrack.album,
    duration: apiTrack.duration,
    filepath: apiTrack.filepath,

    // Optional metadata (null → undefined)
    artworkUrl: apiTrack.artwork_url ?? undefined,
    genre: genre ?? undefined,
    year: apiTrack.year ?? undefined,

    // Navigation and favourites. Dropped until #4568 — every consumer reading
    // track.trackNumber / .albumId got undefined, so album-detail rows rendered
    // without track numbers and "go to album" from a row had nothing to go on.
    albumId: apiTrack.album_id ?? undefined,
    trackNumber: apiTrack.track_number ?? undefined,
    discNumber: apiTrack.disc_number ?? undefined,
    favorite: apiTrack.favorite ?? undefined,

    // Audio properties (snake → camel, null → undefined)
    bitrate: apiTrack.bitrate ?? undefined,
    sampleRate: apiTrack.sample_rate ?? undefined,
    bitDepth: apiTrack.bit_depth ?? undefined,
    channels: apiTrack.channels ?? undefined,
    format: apiTrack.format ?? undefined,
    fileSize: apiTrack.filesize ?? undefined,

    // Analysis properties (null → undefined)
    loudness: apiTrack.loudness ?? undefined,
    crestFactor: apiTrack.crest_factor ?? undefined,
    centroid: apiTrack.centroid ?? undefined,

    // Timestamps (snake → camel, null → undefined). Track.to_dict() — the real
    // ORM path — emits created_at/updated_at; date_added/date_modified come from
    // the DEFAULT_TRACK_FIELDS getattr fallback. Accept either (#4568).
    dateAdded: apiTrack.date_added ?? apiTrack.created_at ?? undefined,
    dateModified: apiTrack.date_modified ?? apiTrack.updated_at ?? undefined
  };
}

/**
 * Transform an array of tracks from API response
 */
export function transformTracks(apiTracks: TrackApiResponse[]): Track[] {
  return apiTracks.map(transformTrack);
}

/**
 * Transform complete tracks API response (with pagination)
 */
export function transformTracksResponse(apiResponse: TracksApiResponse) {
  return {
    tracks: transformTracks(apiResponse.tracks),
    total: apiResponse.total,
    offset: apiResponse.offset,
    limit: apiResponse.limit,
    hasMore: apiResponse.has_more, // snake → camel
  };
}
