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
  return {
    id: apiTrack.id,
    title: apiTrack.title,
    artist: apiTrack.artist,
    album: apiTrack.album,
    duration: apiTrack.duration,
    filepath: apiTrack.filepath,

    // Optional metadata (null → undefined)
    artworkUrl: apiTrack.artwork_url ?? undefined,
    genre: apiTrack.genre ?? undefined,
    year: apiTrack.year ?? undefined,

    // Audio properties (snake → camel, null → undefined)
    bitrate: apiTrack.bitrate ?? undefined,
    sampleRate: apiTrack.sample_rate ?? undefined,
    bitDepth: apiTrack.bit_depth ?? undefined,
    format: apiTrack.format ?? undefined,

    // Analysis properties (null → undefined)
    loudness: apiTrack.loudness ?? undefined,
    crestFactor: apiTrack.crest_factor ?? undefined,
    centroid: apiTrack.centroid ?? undefined,

    // Timestamps (snake → camel, null → undefined)
    dateAdded: apiTrack.date_added ?? undefined,
    dateModified: apiTrack.date_modified ?? undefined
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
