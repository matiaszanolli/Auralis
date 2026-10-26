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
  artist: string | null; // null when the album has no artist (#5905)
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
  // Track serializers may add fields during rolling backend/frontend deploys;
  // explicit properties below remain the supported contract.
  [key: string]: unknown;
  id: number;
  title: string;
  // Track.to_dict() returns arrays only (#2263, #5823)
  artists?: string[];
  genres?: string[];
  album: string | null;
  duration: number; // seconds
  /**
   * Optional: no transport populates it. Track.to_dict() omits it and
   * player_state.TrackInfo marks it Field(exclude=True) (#3205, #4586).
   */
  filepath?: string;

  // Optional metadata — backend sends null for missing values (Python None → JSON null)
  artwork_url?: string | null;
  year?: number | null;

  // Navigation and favourites — in Track.to_dict() since #2851; the
  // transformer dropped them until #4568.
  album_id?: number | null;
  track_number?: number | null;
  disc_number?: number | null;
  favorite?: boolean;

  // Audio properties
  sample_rate?: number | null; // snake_case
  channels?: number | null;
  format?: string | null;
  filesize?: number | null; // → fileSize

  // Timestamps
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
