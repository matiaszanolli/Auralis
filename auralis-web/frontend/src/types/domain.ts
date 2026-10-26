/**
 * Domain Models
 *
 * Core data models used throughout the application.
 * These represent the authoritative shape of data from the backend.
 */

// ============================================================================
// Track
// ============================================================================

export interface Track {
  id: number;
  title: string;
  artist: string;
  album: string;
  duration: number; // Seconds
  /**
   * Server-side path. #4586: declared required here for a long time, but no
   * transport ever populates it — `Track.to_dict()` omits it and
   * `player_state.TrackInfo` marks it `Field(exclude=True)` (#3205, to avoid
   * leaking server paths). Optional so the type states what the backend
   * actually guarantees; prefer `format` for format-aware logic.
   */
  filepath?: string;

  // Optional metadata — backend sends null for missing values (Python None → JSON null)
  artworkUrl?: string | null; // camelCase
  genre?: string | null;
  year?: number | null;
  trackNumber?: number | null; // Backend: track_number
  discNumber?: number | null; // Backend: disc_number
  albumId?: number | null; // Backend: album_id
  favorite?: boolean; // Backend: favorite

  // Audio properties
  sampleRate?: number | null; // Hz (camelCase)
  channels?: number | null;
  format?: string | null; // wav, flac, mp3, etc.
  fileSize?: number | null; // Backend: filesize

  // Timestamps
  dateAdded?: string | null; // ISO 8601 (camelCase)
  dateModified?: string | null; // ISO 8601 (camelCase)
}

// Named subsets for components that only need specific fields
export type PlayerTrack = Pick<Track, 'id' | 'title' | 'artist' | 'album' | 'duration' | 'artworkUrl'>;
export type QueueTrack = Pick<Track, 'id' | 'title' | 'artist' | 'album' | 'duration' | 'artworkUrl'>;
export type LibraryTrack = Pick<Track, 'id' | 'title' | 'artist' | 'album' | 'albumId' | 'duration' | 'filepath' | 'artworkUrl' | 'genre' | 'year' | 'favorite'>;
export type DetailTrack = Pick<Track, 'id' | 'title' | 'artist' | 'album' | 'duration' | 'filepath' | 'artworkUrl' | 'genre' | 'year' | 'trackNumber' | 'discNumber' | 'albumId' | 'favorite'>;
export type TrackRef = Pick<Track, 'id'>;

// ============================================================================
// Album
// ============================================================================

export interface Album {
  id: number;
  title: string;
  artist: string;
  artistId?: number; // FK for album→artist navigation

  // Optional metadata
  artworkUrl?: string; // camelCase
  year?: number;
  // No `genre` (#4709): Album has no genre column — genre lives on Track via
  // the track_genre association — so neither serialize_album nor
  // serialize_album_detail can populate one. Declaring it here advertised a
  // field the backend never sends. Re-add alongside a real derivation (e.g.
  // the modal genre across the album's tracks), not before.

  // Stats
  trackCount: number; // camelCase
  totalDuration?: number; // seconds (NEW - from backend total_duration)

  // Timestamps
  dateAdded?: string; // ISO 8601 (camelCase)
}

// ============================================================================
// Artist
// ============================================================================

export interface Artist {
  id: number;
  name: string;

  // Optional metadata — backend sends null for missing values
  artworkUrl?: string | null; // camelCase

  // Stats
  trackCount: number; // camelCase
  albumCount: number; // camelCase

  // Timestamps
  dateAdded?: string | null; // ISO 8601 (camelCase)
}

// ============================================================================
// Enhancement Settings
// ============================================================================

// Narrowed to a single preset: 'gentle'/'warm'/'bright'/'punchy' are gone,
// not just unlisted -- the backend's schemas.VALID_PRESETS/
// EnhancementPresetLiteral (the single source of truth this mirrors) was
// narrowed the same way (#4861 follow-up).
export type EnhancementPreset = 'adaptive';

export const ENHANCEMENT_PRESETS: EnhancementPreset[] = [
  'adaptive',
];

/**
 * Runtime guard for a preset off the wire, derived from ENHANCEMENT_PRESETS so
 * it cannot drift from the union (#5610). Every plain-string wire field
 * narrows through this instead of an `as EnhancementPreset` cast.
 */
export const isEnhancementPreset = (value: unknown): value is EnhancementPreset =>
  ENHANCEMENT_PRESETS.includes(value as EnhancementPreset);

// ============================================================================
// Audio Fingerprint
// ============================================================================
// Canonical AudioFingerprint is the 25D schema defined in
// '@/utils/fingerprintToGradient'.
export type { AudioFingerprint } from '@/utils/fingerprintToGradient';

// ============================================================================
// Library Stats
// ============================================================================

export interface LibraryStats {
  total_tracks: number;
  total_artists: number;
  total_albums: number;
  total_genres: number;
  total_playlists: number;
  total_duration: number;
  total_duration_formatted: string;
  total_filesize: number;
  total_filesize_gb: number;
  total_plays: number;
  favorite_count: number;
  average_dr?: number | null;
  avg_dr_rating?: number | null;
}
