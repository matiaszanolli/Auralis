/**
 * Backend API Response Types
 *
 * These types represent the EXACT shape of data returned from the backend API.
 * Backend uses snake_case for all field names.
 *
 * DO NOT use these types in React components - use domain types instead.
 * These are only for transformation layer.
 */

// ============================================================================
// Album API Response
// ============================================================================

export interface AlbumApiResponse {
  id: number;
  title: string;
  artist: string;
  year: number | null;
  artwork_path: string | null; // Backend field name
  track_count: number; // Backend field name (snake_case)
  total_duration: number; // Backend field name (snake_case)
}

export interface AlbumsApiResponse {
  albums: AlbumApiResponse[];
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
}

// ============================================================================
// Artist API Response
// ============================================================================

export interface ArtistApiResponse {
  id: number;
  name: string;
  artwork_url: string | null; // Backend field name (issue #2110: was incorrectly artwork_path)
  track_count: number; // snake_case
  album_count: number; // snake_case
  date_added?: string;
}

export interface ArtistsApiResponse {
  artists: ArtistApiResponse[];
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
}

// ============================================================================
// Track API Response
// ============================================================================

export interface TrackApiResponse {
  id: number;
  title: string;
  // Backend to_dict() returns arrays; singular forms kept for backward compat (fixes #2263)
  artists?: string[];   // backend primary field
  genres?: string[];    // backend primary field
  artist?: string;      // singular fallback (some serializer paths)
  album: string;
  duration: number; // seconds
  filepath: string;

  // Optional metadata
  artwork_url?: string;
  genre?: string;       // singular fallback
  year?: number;

  // Audio properties
  bitrate?: number;
  sample_rate?: number; // snake_case
  bit_depth?: number; // snake_case
  format?: string;

  // Analysis properties
  loudness?: number;
  crest_factor?: number; // snake_case
  centroid?: number;

  // Timestamps
  date_added?: string; // snake_case
  date_modified?: string; // snake_case
}

export interface TracksApiResponse {
  tracks: TrackApiResponse[];
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
}

// ============================================================================
// Album Detail API Response (with tracks)
// ============================================================================

export interface AlbumDetailApiResponse extends AlbumApiResponse {
  tracks: TrackApiResponse[];
}

// ============================================================================
// Artist Detail API Response (with albums)
// ============================================================================

export interface ArtistDetailApiResponse extends ArtistApiResponse {
  albums: AlbumApiResponse[];
  top_tracks?: TrackApiResponse[]; // snake_case
}
