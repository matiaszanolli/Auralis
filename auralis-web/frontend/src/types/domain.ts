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
  filepath: string;

  // Optional metadata — backend sends null for missing values (Python None → JSON null)
  artworkUrl?: string | null; // camelCase
  genre?: string | null;
  year?: number | null;

  // Audio properties
  bitrate?: number | null; // kbps
  sampleRate?: number | null; // Hz (camelCase)
  bitDepth?: number | null; // bits (camelCase)
  format?: string | null; // wav, flac, mp3, etc.

  // Analysis properties
  loudness?: number | null; // LUFS
  crestFactor?: number | null; // dB (camelCase)
  centroid?: number | null; // Hz

  // Timestamps
  dateAdded?: string | null; // ISO 8601 (camelCase)
  dateModified?: string | null; // ISO 8601 (camelCase)
}

// ============================================================================
// Album
// ============================================================================

export interface Album {
  id: number;
  title: string;
  artist: string;

  // Optional metadata
  artworkUrl?: string; // camelCase
  year?: number;
  genre?: string;

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
// Playlist
// ============================================================================

export interface Playlist {
  id: number;
  name: string;
  description?: string;
  trackCount: number; // transformed from snake_case track_count (fixes #2505)
  isSmart: boolean; // transformed from snake_case is_smart (fixes #2505)

  // Timestamps — optional because backend returns null when the field is unset
  // (fixes #2278: was required string, causing crashes on null created_at)
  createdAt?: string; // ISO 8601 — transformed from created_at (fixes #2505)
  modifiedAt?: string; // ISO 8601 — transformed from modified_at (fixes #2505)
}

export interface PlaylistDetail extends Playlist {
  tracks: Track[];
}

// ============================================================================
// Queue
// ============================================================================

export interface Queue {
  tracks: Track[];
  currentIndex: number;
  isShuffled: boolean;
  repeatMode: 'off' | 'all' | 'one';
}

// ============================================================================
// Player State
// ============================================================================

export interface PlayerState {
  currentTrack: Track | null;
  isPlaying: boolean;
  volume: number; // 0.0 - 1.0
  position: number; // Seconds
  duration: number; // Seconds
  queue: Track[];
  queueIndex: number;
  isLoading: boolean;
  error: string | null;

  // Playback settings
  gapless_enabled: boolean;
  crossfade_enabled: boolean;
  crossfade_duration: number; // Seconds
}

// ============================================================================
// Enhancement Settings
// ============================================================================

export interface EnhancementSettings {
  enabled: boolean;
  preset: EnhancementPreset;
  intensity: number; // 0.0 - 1.0
}

export type EnhancementPreset =
  | 'adaptive'
  | 'gentle'
  | 'warm'
  | 'bright'
  | 'punchy';

export const ENHANCEMENT_PRESETS: EnhancementPreset[] = [
  'adaptive',
  'gentle',
  'warm',
  'bright',
  'punchy',
];

export const ENHANCEMENT_PRESET_NAMES: Record<EnhancementPreset, string> = {
  adaptive: 'Adaptive',
  gentle: 'Gentle',
  warm: 'Warm',
  bright: 'Bright',
  punchy: 'Punchy',
};

export const ENHANCEMENT_PRESET_DESCRIPTIONS: Record<EnhancementPreset, string> = {
  adaptive: 'Automatically optimize for current track',
  gentle: 'Subtle enhancement with minimal change',
  warm: 'Enhance warmth and bass',
  bright: 'Enhance clarity and high frequencies',
  punchy: 'Maximize energy and dynamics',
};

// ============================================================================
// Mastering Recommendation
// ============================================================================

export interface MasteringRecommendation {
  track_id: number;
  primary_profile_id: string;
  primary_profile_name: string;
  confidence_score: number; // 0.0 - 1.0

  // Predicted changes
  predicted_loudness_change: number; // dB
  predicted_crest_change: number; // dB
  predicted_centroid_change: number; // Hz

  // Hybrid blending (if applicable)
  weighted_profiles: Array<{
    profile_id: string;
    profile_name: string;
    weight: number; // 0.0 - 1.0
  }>;

  // Explanation
  reasoning: string;
  is_hybrid: boolean;
}

// ============================================================================
// Audio Fingerprint
// ============================================================================
// Canonical AudioFingerprint is the 25D schema defined in
// '@/utils/fingerprintToGradient'. The old schema (trackId, loudness, crest,
// rms, centroid, spectralFlux, mfcc, chroma, timestamp, cached,
// computation_time_ms) has been removed to eliminate the dual-interface
// conflict (fixes #2280). Import from '@/utils/fingerprintToGradient' instead.
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
  average_lufs?: number | null;
  avg_dr_rating?: number | null;
  avg_lufs?: number | null;
}

// ============================================================================
// Scan Progress
// ============================================================================

export interface ScanProgress {
  current: number; // Files processed
  total: number; // Total files to process
  percentage: number; // 0-100
  current_file?: string;
  eta_seconds?: number;
}

// ============================================================================
// Application State
// ============================================================================

export interface AppState {
  // UI
  isSidebarOpen: boolean;
  currentView: 'library' | 'playlists' | 'queue' | 'settings';
  isEnhancementPaneOpen: boolean;

  // Playback
  player: PlayerState;
  enhancement: EnhancementSettings;

  // Library
  libraryStats: LibraryStats | null;
  isLibraryScanning: boolean;
  scanProgress: ScanProgress | null;

  // Recommendations
  currentRecommendation: MasteringRecommendation | null;

  // Error handling
  errors: AppError[];
  connectionStatus: ConnectionStatus;
}

export type ConnectionStatus =
  | 'connected'
  | 'connecting'
  | 'disconnected'
  | 'error';

// ============================================================================
// Error Models
// ============================================================================

export interface AppError {
  id: string; // Unique ID for dismissing
  type: 'error' | 'warning' | 'info' | 'success';
  message: string;
  details?: string;
  timestamp: number;
  duration?: number; // Auto-dismiss after ms (null = manual)
}

export enum AppErrorType {
  NETWORK_ERROR = 'NETWORK_ERROR',
  NOT_FOUND = 'NOT_FOUND',
  VALIDATION_ERROR = 'VALIDATION_ERROR',
  UNAUTHORIZED = 'UNAUTHORIZED',
  CONFLICT = 'CONFLICT',
  SERVER_ERROR = 'SERVER_ERROR',
  UNKNOWN = 'UNKNOWN',
}

// ============================================================================
// Selection & Filtering
// ============================================================================

export interface Selection {
  ids: Set<number>;
  count: number;
}

export interface FilterOptions {
  search?: string;
  genre?: string;
  year?: number;
  artist?: string;
  album?: string;
  format?: string;
  isCorrupted?: boolean;
}

export interface SortOptions {
  field: 'title' | 'artist' | 'album' | 'duration' | 'date_added' | 'loudness';
  order: 'asc' | 'desc';
}

// ============================================================================
// Pagination
// ============================================================================

export interface PaginationState {
  limit: number;
  offset: number;
  total: number;
  hasMore: boolean;
}

export interface PaginatedResponse<T> {
  data: T[];
  pagination: PaginationState;
}

// ============================================================================
// Type Guards
// ============================================================================

export function isTrack(value: any): value is Track {
  return (
    typeof value === 'object' &&
    typeof value.id === 'number' &&
    typeof value.title === 'string' &&
    typeof value.artist === 'string' &&
    typeof value.album === 'string' &&
    typeof value.duration === 'number'
  );
}

export function isAlbum(value: any): value is Album {
  return (
    typeof value === 'object' &&
    typeof value.id === 'number' &&
    typeof value.title === 'string' &&
    typeof value.artist === 'string' &&
    typeof value.trackCount === 'number' // camelCase
  );
}

export function isArtist(value: any): value is Artist {
  return (
    typeof value === 'object' &&
    typeof value.id === 'number' &&
    typeof value.name === 'string' &&
    typeof value.trackCount === 'number' // camelCase
  );
}

export function isEnhancementPreset(value: any): value is EnhancementPreset {
  return ENHANCEMENT_PRESETS.includes(value);
}

// ============================================================================
// Utility Functions
// ============================================================================

export function formatDuration(seconds: number): string {
  if (!isFinite(seconds)) return '0:00';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

export function parseDuration(formatted: string): number {
  const parts = formatted.split(':').map(p => parseInt(p, 10));
  if (parts.length === 2) {
    return parts[0] * 60 + parts[1];
  }
  if (parts.length === 3) {
    return parts[0] * 3600 + parts[1] * 60 + parts[2];
  }
  return 0;
}

export function getTrackKey(track: Track): string {
  return `track-${track.id}`;
}

export function getAlbumKey(album: Album): string {
  return `album-${album.id}`;
}

export function getArtistKey(artist: Artist): string {
  return `artist-${artist.id}`;
}
