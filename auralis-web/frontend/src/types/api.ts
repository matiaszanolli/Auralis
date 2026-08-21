/**
 * REST API Types
 *
 * TypeScript type definitions for all REST API requests and responses.
 * Maps to: auralis-web/backend/routers/*.py
 */

import type { TrackInfo } from './websocket';

// ============================================================================
// Generic Response Wrappers
// ============================================================================

export interface ApiResponse<T = unknown> {
  data: T;
  error?: string;
  status: number;
}

export interface ApiListResponse<T = unknown> {
  data: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface ApiError {
  status: number;
  message: string;
  /**
   * Optional domain-specific error code (e.g. 'QUEUE_SET_ERROR', 'PLAY_ERROR').
   * Callers use this to disambiguate which user-facing flow failed.
   */
  code?: string;
  details?: Record<string, unknown>;
}

/** Type guard for ApiError — checks structural shape since ApiError is an interface */
export function isApiError(err: unknown): err is ApiError {
  return (
    typeof err === 'object' &&
    err !== null &&
    'status' in err &&
    'message' in err &&
    typeof (err as ApiError).status === 'number' &&
    typeof (err as ApiError).message === 'string'
  );
}

// ============================================================================
// Player API
// ============================================================================

export interface PlayerPlayRequest {
  track_path?: string;
}

export interface PlayerSeekRequest {
  position: number; // Seconds
}

export interface PlayerVolumeRequest {
  /**
   * 0-100 scale, matching the backend's SetVolumeRequest (#3894).
   *
   * This said "0.0 - 1.0", which was never the wire format: the backend clamps
   * to 0-100 and PlayerState.volume defaults to 80. The production call site
   * (usePlaybackControl.setVolume) already sends `Math.round(v * 100)`, so the
   * runtime was correct and only the type comment lied.
   *
   * Note this is the *player* endpoint's scale. It is deliberately not claimed
   * as project-wide: settings.py's SettingsUpdateRequest.volume really is
   * 0.0-1.0, a genuine backend-to-backend disagreement tracked by #4711.
   */
  volume: number;
}

export interface PlayerQueueAddRequest {
  track_path: string;
}

export interface PlayerQueueRemoveRequest {
  index: number;
}

export interface PlayerQueueReorderRequest {
  from_index: number;
  to_index: number;
}

/*
 * The `PlayerState` interface that lived here was removed in #3894.
 *
 * It was a third declaration of the same shape, alongside `domain.PlayerState`
 * and `ws/player.PlayerStateData`, with nothing importing it. Three same-named
 * types meant an IDE would autocomplete whichever it found first, and the
 * duplicate had no volume-unit annotation at all.
 *
 * The authoritative wire-facing shape is `PlayerStateData` in `types/ws/player`,
 * produced by `transformPlayerState()` from the backend's snake_case payload.
 * Import that instead of redeclaring it here.
 */

export interface MasteringRecommendationResponse {
  track_id: number;
  primary_profile_id: string;
  primary_profile_name: string;
  confidence_score: number;
  predicted_loudness_change: number;
  predicted_crest_change: number;
  predicted_centroid_change: number;
  weighted_profiles: Array<{
    profile_id: string;
    profile_name: string;
    weight: number;
  }>;
  reasoning: string;
  is_hybrid: boolean;
}

// ============================================================================
// Library API
// ============================================================================

export interface LibraryQueryParams {
  view: 'tracks' | 'albums' | 'artists';
  limit?: number;
  offset?: number;
  search?: string;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
}

export interface LibraryTracksResponse extends ApiListResponse {
  data: TrackInfo[];
}

/**
 * REMOVED: Album, Artist, AlbumsResponse, ArtistsResponse, AlbumDetail, ArtistDetail
 *
 * These types are now redundant due to transformation layer (Phase 2-7).
 *
 * Use instead:
 * - Backend API types: import from '@/api/transformers' (AlbumApiResponse, ArtistApiResponse)
 * - Domain models: import from '@/types/domain' (Album, Artist)
 *
 * This file now contains ONLY:
 * - Generic API wrappers (ApiResponse, ApiListResponse, ApiError)
 * - Request/response types for endpoints without transformers yet
 */

// LibraryScanRequest/LibraryScanResponse removed (#4372) — diverged from the
// backend contract (backend takes {directories: list[str]} and returns
// ScanResultResponse) and had zero importers. Real scan consumers use the
// actual backend shapes directly.

export type { LibraryStats as LibraryStatsResponse } from './domain';

// ============================================================================
// Metadata API
// ============================================================================

// MetadataUpdateRequest / MetadataBatchUpdate{Request,Response} /
// MetadataUpdateResponse removed (#4372) — structurally incompatible with the
// backend metadata router and consumed by no fetch site.

// ============================================================================
// Enhancement API
// ============================================================================

export interface EnhancementSettingsRequest {
  enabled: boolean;
  preset: 'adaptive' | 'gentle' | 'warm' | 'bright' | 'punchy';
  intensity: number; // 0.0 - 1.0
}

// EnhancementSettingsResponse removed (#4372) — backend returns
// {message, settings:{...}} (nested), not this flat shape; no importers.

/*
 * Renamed from `EnhancementPreset` in #4942, same reasoning as the
 * `PlayerState` note above.
 *
 * `domain.EnhancementPreset` is the string-literal union used as a settings
 * VALUE ('adaptive' | 'gentle' | ...). This is a different thing entirely: a
 * preset DESCRIPTOR row returned by GET /api/enhancement/presets. Two
 * structurally incompatible types sharing one name meant an IDE auto-import on
 * a bare `EnhancementPreset` could silently pick the wrong one — and unlike a
 * shape duplicate, a union resolving where an object was meant (or vice versa)
 * fails in confusing places far from the import.
 *
 * The union keeps the plain name because it is what application code passes
 * around; this one carries the `Info` suffix.
 */
export interface EnhancementPresetInfo {
  id: string;
  name: string;
  description: string;
  icon?: string;
  is_default: boolean;
}

export interface EnhancementPresetsResponse {
  presets: EnhancementPresetInfo[];
}

// ============================================================================
// Playlist API
// ============================================================================

export interface Playlist {
  id: number;
  name: string;
  description?: string;
  track_count: number;
  created_at: string;
  modified_at: string;
  is_smart: boolean;
}

export interface PlaylistCreateRequest {
  name: string;
  description?: string;
}

export interface PlaylistCreateResponse extends Playlist {}

export interface PlaylistUpdateRequest {
  name?: string;
  description?: string;
}

export interface PlaylistAddTracksRequest {
  track_ids: number[];
}

export interface PlaylistAddTracksResponse {
  added_count: number;
  playlist_id: number;
}

export interface PlaylistRemoveTrackRequest {
  track_id: number;
}

export interface PlaylistDetail extends Playlist {
  tracks: TrackInfo[];
}

// ============================================================================
// Artwork API
// ============================================================================

export interface ArtworkUpdateRequest {
  artwork_url?: string; // URL or base64 data
}

export interface ArtworkUpdateResponse {
  success: boolean;
  artwork_url: string;
  cached: boolean;
}

// ============================================================================
// Search API
// ============================================================================

export interface SearchQuery {
  q: string; // Search query
  type?: 'tracks' | 'albums' | 'artists' | 'all';
  limit?: number;
}

export interface SearchResult {
  tracks: TrackInfo[];
  albums: import('@/types/domain').Album[];
  artists: import('@/types/domain').Artist[];
  query: string;
  execution_time_ms: number;
}

// ============================================================================
// Similarity / Fingerprinting API
// ============================================================================

export interface Fingerprint {
  trackId: number;
  loudness: number;
  crest: number;
  centroid: number;
  spectralFlux: number[];
  mfcc: number[][];
  chroma: number[][];
  timestamp: number;
}

export interface FingerprintResponse {
  track_id: number;
  fingerprint: Fingerprint;
  cached: boolean;
  computation_time_ms: number;
}

// SimilarTracksRequest / SimilarTrack / SimilarTracksResponse removed (#4372)
// — the api.ts SimilarTrack was nested ({track, similarity_score}) while the
// backend returns a flat shape; every real consumer imports SimilarTrack from
// '@/hooks/fingerprint' instead. A second frontend SimilarTrack variant lived
// at '@/services/similarityService' with a `duration` field the backend never
// populated (#4674) — that whole service had zero production importers (its
// only consumer, components/features/discovery/, was dead code already
// deleted) and was removed rather than wired up.

// ============================================================================
// Health & Status API
// ============================================================================

/** Matches GET /api/health → HealthResponse (schemas.py, fixes #3976 / TS-5). */
export interface HealthCheckResponse {
  status: string;
  auralis_available: boolean;
}

/**
 * Cache statistics from `/api/cache/stats`.
 *
 * #3593: previously declared `overall.hit_rate` but every real consumer reads
 * `overall.overall_hit_rate`. Aligned with the canonical `CacheStats` type in
 * services/api/standardizedAPIClient.ts and the actual backend payload.
 * Added `total_hits` / `total_misses` / `tracks` to match runtime.
 */
export interface CacheStatsResponse {
  tier1: {
    chunks: number;
    size_mb: number;
    hits: number;
    misses: number;
    hit_rate: number;
  };
  tier2: {
    chunks: number;
    size_mb: number;
    hits: number;
    misses: number;
    hit_rate: number;
  };
  overall: {
    total_chunks: number;
    total_size_mb: number;
    total_hits: number;
    total_misses: number;
    overall_hit_rate: number;
    tracks_cached: number;
  };
  tracks?: Record<string, {
    track_id: number;
    completion_percent: number;
    fully_cached: boolean;
  }>;
}

// ============================================================================
// Streaming API
// ============================================================================

export interface StreamingUrlRequest {
  track_id: number;
  format?: 'webm' | 'mp3' | 'wav';
}

export interface StreamingUrlResponse {
  track_id: number;
  url: string;
  format: string;
  content_length: number;
  expires_in_seconds?: number;
}

// ============================================================================
// Error Handling
// ============================================================================

export class ApiErrorHandler {
  static parse(error: unknown): ApiError {
    if (error instanceof Error) {
      // useRestAPI attaches the real status as a property so the message can be
      // the backend's `detail` text instead of 'HTTP nnn: ...' (#4831). Fall back
      // to scraping the legacy generic message for any thrower that still uses
      // it, so callers keep seeing the actual code rather than always 500 (#2361).
      const attached = (error as { status?: unknown }).status;
      if (typeof attached === 'number') {
        return { status: attached, message: error.message };
      }
      const httpMatch = error.message.match(/^HTTP (\d{3}):/);
      return {
        status: httpMatch ? parseInt(httpMatch[1], 10) : 500,
        message: error.message,
      };
    }

    if (typeof error === 'object' && error !== null && 'status' in error && 'message' in error) {
      return error as ApiError;
    }

    return {
      status: 500,
      message: 'Unknown error',
      details: { raw: String(error) },
    };
  }

  /**
   * #3594: like parse() but lets the caller stamp on a domain-specific
   * `code` so existing per-hook code-strings stay observable.
   */
  static parseWithCode(error: unknown, code: string): ApiError {
    return { ...ApiErrorHandler.parse(error), code };
  }

  static isNetworkError(error: ApiError): boolean {
    return error.status === 0 || error.status >= 500;
  }

  static isClientError(error: ApiError): boolean {
    return error.status >= 400 && error.status < 500;
  }

  static isNotFound(error: ApiError): boolean {
    return error.status === 404;
  }

  static isUnauthorized(error: ApiError): boolean {
    return error.status === 401 || error.status === 403;
  }

  static isValidationError(error: ApiError): boolean {
    return error.status === 422;
  }
}

// ============================================================================
// Query Parameters Builder
// ============================================================================

/**
 * Acceptable value types for query-param serialization.
 * #3635: narrowed from `any` to prevent silent `[object Object]` coercion
 * when a caller passes a nested object by mistake.
 */
export type QueryParamValue =
  | string
  | number
  | boolean
  | null
  | undefined
  | ReadonlyArray<string | number | boolean>;

export function buildQueryParams(params: Record<string, QueryParamValue>): string {
  const searchParams = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== '') {
      if (Array.isArray(value)) {
        value.forEach(v => searchParams.append(key, String(v)));
      } else {
        searchParams.set(key, String(value));
      }
    }
  }

  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : '';
}
