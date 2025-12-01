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

  // Optional metadata
  artwork_url?: string;
  genre?: string;
  year?: number;

  // Audio properties
  bitrate?: number; // kbps
  sample_rate?: number; // Hz
  bit_depth?: number; // bits
  format?: string; // wav, flac, mp3, etc.

  // Analysis properties
  loudness?: number; // LUFS
  crest_factor?: number; // dB
  centroid?: number; // Hz

  // Timestamps
  date_added?: string; // ISO 8601
  date_modified?: string; // ISO 8601
}

// ============================================================================
// Album
// ============================================================================

export interface Album {
  id: number;
  title: string;
  artist: string;

  // Optional metadata
  artwork_url?: string;
  year?: number;
  genre?: string;

  // Stats
  track_count: number;

  // Timestamps
  date_added?: string; // ISO 8601
}

// ============================================================================
// Artist
// ============================================================================

export interface Artist {
  id: number;
  name: string;

  // Optional metadata
  artwork_url?: string;

  // Stats
  track_count: number;
  album_count: number;

  // Timestamps
  date_added?: string; // ISO 8601
}

// ============================================================================
// Playlist
// ============================================================================

export interface Playlist {
  id: number;
  name: string;
  description?: string;
  track_count: number;
  is_smart: boolean;

  // Timestamps
  created_at: string; // ISO 8601
  modified_at: string; // ISO 8601
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

export interface AudioFingerprint {
  trackId: number;

  // Loudness analysis
  loudness: number; // LUFS

  // Dynamics analysis
  crest: number; // dB
  rms: number; // LUFS

  // Spectral analysis
  centroid: number; // Hz
  spectralFlux: number[]; // Per chunk
  mfcc: number[][]; // Mel-frequency cepstral coefficients

  // Harmonic analysis
  chroma: number[][]; // Chromatic pitch distribution

  // Metadata
  timestamp: number; // Unix timestamp (milliseconds)
  cached: boolean;
  computation_time_ms: number;
}

// ============================================================================
// Library Stats
// ============================================================================

export interface LibraryStats {
  total_tracks: number;
  total_albums: number;
  total_artists: number;
  total_size_mb: number;
  average_bitrate: number;
  supported_formats: string[];
  total_duration_seconds: number;
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
    typeof value.track_count === 'number'
  );
}

export function isArtist(value: any): value is Artist {
  return (
    typeof value === 'object' &&
    typeof value.id === 'number' &&
    typeof value.name === 'string' &&
    typeof value.track_count === 'number'
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
