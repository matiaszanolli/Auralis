/**
 * Track Transformer
 *
 * Transforms backend API track data (snake_case) to frontend domain models (camelCase).
 */

import type { TrackApiResponse } from './types';
import type { Track } from '@/types/domain';

/**
 * Transform a single track from API response to domain model
 *
 * Backend contract (snake_case):
 * - sample_rate, bit_depth, created_at, updated_at
 *
 * Frontend domain (camelCase):
 * - sampleRate, bitDepth, dateAdded, dateModified
 */
export function transformTrack(apiTrack: TrackApiResponse): Track {
  // Track.to_dict() sends artists/genres as arrays and no singular twin (#2263,
  // #5823): the first entry is the display value.
  const artist = apiTrack.artists?.[0] ?? '';
  const genre = apiTrack.genres?.[0];

  return {
    id: apiTrack.id,
    title: apiTrack.title,
    artist,
    // Albumless tracks are valid backend responses; normalize them at the
    // API boundary so domain consumers can keep using a string.
    album: apiTrack.album ?? '',
    // Backend TrackResponse.duration is `float | None` — the REST path
    // reaches this mapper through an untyped response.json(), so a null
    // would poison player.duration (setCurrentTime clamps with
    // Math.min(x, null) === 0) (#5606). Normalize like album above.
    duration: apiTrack.duration ?? 0,
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

    // Analysis properties (null → undefined). Track.to_dict() names the
    // integrated loudness lufs_level; there is no `loudness` key (#5823).
    loudness: apiTrack.lufs_level ?? undefined,

    // Timestamps (snake → camel, null → undefined)
    dateAdded: apiTrack.created_at ?? undefined,
    dateModified: apiTrack.updated_at ?? undefined
  };
}

/**
 * Transform an array of tracks from API response
 */
export function transformTracks(apiTracks: TrackApiResponse[]): Track[] {
  return apiTracks.map(transformTrack);
}

