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
  artist_id: number | null; // FK to artists table (snake_case)
  year: number | null;
  artwork_url: string | null; // Backend field name
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
  /**
   * ISO timestamp of when the artist row was created. The artists router names
   * this `created_at` (from `Artist.to_dict()`), not `date_added` as tracks do
   * — this type declared the track spelling, which no artist response has ever
   * carried, so `dateAdded` was always undefined (#4833).
   */
  created_at?: string | null;
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
  /**
   * Optional: no transport populates it. Track.to_dict() omits it and
   * player_state.TrackInfo marks it Field(exclude=True) (#3205, #4586).
   */
  filepath?: string;

  // Optional metadata — backend sends null for missing values (Python None → JSON null)
  artwork_url?: string | null;
  genre?: string | null;       // singular fallback
  year?: number | null;

  // Navigation and favourites — present in both Track.to_dict() and
  // DEFAULT_TRACK_FIELDS since #2851; the transformer dropped them until #4568.
  album_id?: number | null;
  track_number?: number | null;
  disc_number?: number | null;
  favorite?: boolean;

  // Audio properties
  bitrate?: number | null;
  sample_rate?: number | null; // snake_case
  bit_depth?: number | null; // snake_case
  channels?: number | null;
  format?: string | null;
  filesize?: number | null; // → fileSize

  // Analysis properties
  loudness?: number | null;
  crest_factor?: number | null; // snake_case
  centroid?: number | null;

  /**
   * Timestamps. `Track.to_dict()` (the real ORM path) emits created_at /
   * updated_at; date_added / date_modified only appear on the
   * DEFAULT_TRACK_FIELDS getattr fallback. Both are accepted (#4568).
   */
  date_added?: string | null; // snake_case
  date_modified?: string | null; // snake_case
  created_at?: string | null;
  updated_at?: string | null;
}

export interface TracksApiResponse {
  tracks: TrackApiResponse[];
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
}

// ============================================================================
// Artist Detail API Response (#2844: matches backend ArtistDetailResponse shape)
// ============================================================================

// Deliberately NOT AlbumApiResponse (#4752): the backend's nested
// `AlbumInArtist` model (routers/artists.py) only carries these 5 fields —
// response_model strips artist/artist_id/artwork_url before they ever reach
// the wire, so promising the full AlbumApiResponse shape here is a type lie.
export interface AlbumInArtistApiResponse {
  id: number;
  title: string;
  year: number | null;
  track_count: number;
  total_duration: number;
}

export interface ArtistDetailApiResponse {
  id: number;
  name: string;
  albums: AlbumInArtistApiResponse[];
  total_albums: number;
  total_tracks: number;
  artwork_url?: string | null;
  artwork_source?: string | null;
}
