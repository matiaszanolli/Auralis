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

    // Optional metadata (direct mapping)
    artworkUrl: apiTrack.artwork_url,
    genre: apiTrack.genre,
    year: apiTrack.year,

    // Audio properties (snake → camel)
    bitrate: apiTrack.bitrate,
    sampleRate: apiTrack.sample_rate, // snake → camel
    bitDepth: apiTrack.bit_depth, // snake → camel
    format: apiTrack.format,

    // Analysis properties
    loudness: apiTrack.loudness,
    crestFactor: apiTrack.crest_factor, // snake → camel
    centroid: apiTrack.centroid,

    // Timestamps (snake → camel)
    dateAdded: apiTrack.date_added, // snake → camel
    dateModified: apiTrack.date_modified, // snake → camel
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
