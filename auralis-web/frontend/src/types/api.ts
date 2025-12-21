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

export interface ApiResponse<T = any> {
  data: T;
  error?: string;
  status: number;
}

export interface ApiListResponse<T = any> {
  data: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface ApiError {
  status: number;
  message: string;
  details?: Record<string, any>;
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
  volume: number; // 0.0 - 1.0
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

export interface PlayerState {
  currentTrack: TrackInfo | null;
  isPlaying: boolean;
  volume: number;
  position: number;
  duration: number;
  queue: TrackInfo[];
  queueIndex: number;
  gapless_enabled: boolean;
  crossfade_enabled: boolean;
  crossfade_duration: number;
}

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

export interface LibraryScanRequest {
  directory?: string; // Optional: specific directory to scan
}

export interface LibraryScanResponse {
  scan_id: string;
  status: 'started' | 'in_progress' | 'completed';
  progress: number; // 0-100
}

export interface LibraryStatsResponse {
  total_tracks: number;
  total_albums: number;
  total_artists: number;
  total_size_mb: number;
  average_bitrate: number;
  supported_formats: string[];
}

// ============================================================================
// Metadata API
// ============================================================================

export interface MetadataUpdateRequest {
  title?: string;
  artist?: string;
  album?: string;
  genre?: string;
  year?: number;
  [key: string]: any; // Allow additional fields
}

export interface MetadataBatchUpdateRequest {
  track_ids: number[];
  updates: MetadataUpdateRequest;
}

export interface MetadataUpdateResponse {
  track_id: number;
  updated_fields: string[];
  success: boolean;
}

export interface MetadataBatchUpdateResponse {
  updated_count: number;
  failed_count: number;
  details: MetadataUpdateResponse[];
}

// ============================================================================
// Enhancement API
// ============================================================================

export interface EnhancementSettingsRequest {
  enabled: boolean;
  preset: 'adaptive' | 'gentle' | 'warm' | 'bright' | 'punchy';
  intensity: number; // 0.0 - 1.0
}

export interface EnhancementSettingsResponse {
  enabled: boolean;
  preset: 'adaptive' | 'gentle' | 'warm' | 'bright' | 'punchy';
  intensity: number;
  last_updated: string; // ISO timestamp
}

export interface EnhancementPreset {
  id: string;
  name: string;
  description: string;
  icon?: string;
  is_default: boolean;
}

export interface EnhancementPresetsResponse {
  presets: EnhancementPreset[];
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
  albums: Album[];
  artists: Artist[];
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

export interface SimilarTracksRequest {
  track_id: number;
  limit?: number;
  threshold?: number; // 0.0 - 1.0
}

export interface SimilarTrack {
  track: TrackInfo;
  similarity_score: number; // 0.0 - 1.0
}

export interface SimilarTracksResponse {
  query_track: TrackInfo;
  similar_tracks: SimilarTrack[];
  execution_time_ms: number;
}

// ============================================================================
// Health & Status API
// ============================================================================

export interface HealthCheckResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  version: string;
  uptime_seconds: number;
  database_connected: boolean;
  cache_healthy: boolean;
  websocket_connected: boolean;
}

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
    hit_rate: number;
    tracks_cached: number;
  };
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
  static parse(error: any): ApiError {
    if (error instanceof Error) {
      return {
        status: 500,
        message: error.message,
      };
    }

    if (typeof error === 'object' && 'status' in error && 'message' in error) {
      return error as ApiError;
    }

    return {
      status: 500,
      message: 'Unknown error',
      details: error,
    };
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

export function buildQueryParams(params: Record<string, any>): string {
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
