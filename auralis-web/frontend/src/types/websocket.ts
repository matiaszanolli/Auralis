/**
 * WebSocket API Types
 *
 * Complete TypeScript type definitions for all WebSocket messages.
 * See: auralis-web/backend/WEBSOCKET_API.md for protocol specification.
 */

// ============================================================================
// Message Type Union
// ============================================================================

export type WebSocketMessageType =
  // Player state messages
  | 'player_state'
  | 'playback_started'
  | 'playback_paused'
  | 'playback_stopped'
  | 'track_loaded'
  | 'track_changed'
  | 'position_changed'
  | 'volume_changed'
  // Queue messages
  | 'queue_updated'
  | 'queue_changed'
  | 'queue_shuffled'
  | 'repeat_mode_changed'
  // Library messages
  | 'library_updated'
  // Metadata messages
  | 'metadata_updated'
  | 'metadata_batch_updated'
  // Playlist messages
  | 'playlist_created'
  | 'playlist_updated'
  | 'playlist_deleted'
  // Enhancement messages
  | 'enhancement_settings_changed'
  | 'mastering_recommendation'
  // Artwork messages
  | 'artwork_updated'
  // System messages
  | 'scan_progress'
  | 'scan_complete';

// ============================================================================
// Base Message Interface
// ============================================================================

export interface WebSocketMessage<T = any> {
  type: WebSocketMessageType;
  data: T;
  timestamp?: number;
}

// ============================================================================
// Player State Messages
// ============================================================================

/**
 * Player state data (frontend-facing camelCase representation).
 *
 * IMPORTANT: The backend sends snake_case fields (current_track, is_playing, queue_index).
 * You must map snake_case → camelCase when consuming this data.
 *
 * See usePlayerStateSync.ts and usePlaybackState.ts for mapping examples.
 */
export interface PlayerStateData {
  currentTrack: TrackInfo | null;
  isPlaying: boolean;
  volume: number; // 0.0 - 1.0
  position: number; // Seconds
  duration: number; // Seconds
  queue: TrackInfo[];
  queueIndex: number;
  gapless_enabled: boolean;
  crossfade_enabled: boolean;
  crossfade_duration: number; // Seconds
}

export interface PlayerStateMessage extends WebSocketMessage {
  type: 'player_state';
  data: PlayerStateData;
}

export interface PlaybackStartedMessage extends WebSocketMessage {
  type: 'playback_started';
  data: {
    state: 'playing';
  };
}

export interface PlaybackPausedMessage extends WebSocketMessage {
  type: 'playback_paused';
  data: {
    state: 'paused';
  };
}

export interface PlaybackStoppedMessage extends WebSocketMessage {
  type: 'playback_stopped';
  data: {
    state: 'stopped';
  };
}

export interface TrackLoadedMessage extends WebSocketMessage {
  type: 'track_loaded';
  data: {
    track_path: string;
  };
}

export interface TrackChangedMessage extends WebSocketMessage {
  type: 'track_changed';
  data: {
    action: 'next' | 'previous';
  };
}

export interface PositionChangedMessage extends WebSocketMessage {
  type: 'position_changed';
  data: {
    position: number; // Seconds
  };
}

export interface VolumeChangedMessage extends WebSocketMessage {
  type: 'volume_changed';
  data: {
    volume: number; // 0.0 - 1.0
  };
}

// ============================================================================
// Queue Messages
// ============================================================================

export interface QueueUpdatedMessage extends WebSocketMessage {
  type: 'queue_updated';
  data: {
    action: 'added' | 'removed' | 'reordered' | 'cleared' | 'shuffled';
    track_path?: string; // For "added" action
    index?: number; // For "removed" action
    queue_size: number;
  };
}

/**
 * Broadcast when queue contents change (add, remove, reorder, or clear)
 */
export interface QueueChangedMessage extends WebSocketMessage {
  type: 'queue_changed';
  data: {
    tracks: TrackInfo[]; // Full queue after change
    currentIndex: number; // Current position in queue
    action: 'added' | 'removed' | 'reordered' | 'cleared';
  };
}

/**
 * Broadcast when shuffle mode is toggled
 */
export interface QueueShuffledMessage extends WebSocketMessage {
  type: 'queue_shuffled';
  data: {
    isShuffled: boolean;
    tracks?: TrackInfo[]; // Reordered queue if shuffled
  };
}

/**
 * Broadcast when repeat mode changes
 */
export interface RepeatModeChangedMessage extends WebSocketMessage {
  type: 'repeat_mode_changed';
  data: {
    repeatMode: 'off' | 'all' | 'one';
  };
}

// ============================================================================
// Library Messages
// ============================================================================

export interface LibraryUpdatedMessage extends WebSocketMessage {
  type: 'library_updated';
  data: {
    action: 'scan' | 'import' | 'update';
    track_count?: number;
    album_count?: number;
    artist_count?: number;
  };
}

// ============================================================================
// Metadata Messages
// ============================================================================

export interface MetadataUpdatedMessage extends WebSocketMessage {
  type: 'metadata_updated';
  data: {
    track_id: number;
    updated_fields: string[]; // e.g., ["title", "artist", "album"]
  };
}

export interface MetadataBatchUpdatedMessage extends WebSocketMessage {
  type: 'metadata_batch_updated';
  data: {
    track_ids: number[];
    count: number;
  };
}

// ============================================================================
// Playlist Messages
// ============================================================================

export interface PlaylistCreatedMessage extends WebSocketMessage {
  type: 'playlist_created';
  data: {
    playlist_id: number;
    name: string;
  };
}

export interface PlaylistUpdatedMessage extends WebSocketMessage {
  type: 'playlist_updated';
  data: {
    playlist_id: number;
    action: 'renamed' | 'track_added' | 'track_removed' | 'reordered' | 'cleared';
  };
}

export interface PlaylistDeletedMessage extends WebSocketMessage {
  type: 'playlist_deleted';
  data: {
    playlist_id: number;
  };
}

// ============================================================================
// Enhancement Messages
// ============================================================================

export interface EnhancementSettingsChangedMessage extends WebSocketMessage {
  type: 'enhancement_settings_changed';
  data: {
    enabled: boolean;
    preset: 'adaptive' | 'gentle' | 'warm' | 'bright' | 'punchy';
    intensity: number; // 0.0 - 1.0
  };
}

export interface MasteringRecommendationData {
  track_id: number;
  primary_profile_id: string;
  primary_profile_name: string;
  confidence_score: number; // 0.0 - 1.0
  predicted_loudness_change: number; // dB
  predicted_crest_change: number; // dB
  predicted_centroid_change: number; // Hz
  weighted_profiles: Array<{
    profile_id: string;
    profile_name: string;
    weight: number; // 0.0 - 1.0, sum of all = 1.0
  }>;
  reasoning: string;
  is_hybrid: boolean;
}

export interface MasteringRecommendationMessage extends WebSocketMessage {
  type: 'mastering_recommendation';
  data: MasteringRecommendationData;
}

// ============================================================================
// Artwork Messages
// ============================================================================

export interface ArtworkUpdatedMessage extends WebSocketMessage {
  type: 'artwork_updated';
  data: {
    action: 'extracted' | 'downloaded' | 'deleted';
    album_id: number;
    artwork_path?: string; // absent for 'deleted'
  };
}

// ============================================================================
// System Messages
// ============================================================================

export interface ScanProgressMessage extends WebSocketMessage {
  type: 'scan_progress';
  data: {
    current: number; // Files processed
    total: number; // Total files
    percentage: number; // 0-100
    current_file?: string;
  };
}

export interface ScanCompleteMessage extends WebSocketMessage {
  type: 'scan_complete';
  data: {
    files_processed: number;
    tracks_added: number;
    duration: number; // Seconds
  };
}

// ============================================================================
// Union Type for All Messages
// ============================================================================

export type AnyWebSocketMessage =
  | PlayerStateMessage
  | PlaybackStartedMessage
  | PlaybackPausedMessage
  | PlaybackStoppedMessage
  | TrackLoadedMessage
  | TrackChangedMessage
  | PositionChangedMessage
  | VolumeChangedMessage
  | QueueUpdatedMessage
  | QueueChangedMessage
  | QueueShuffledMessage
  | RepeatModeChangedMessage
  | LibraryUpdatedMessage
  | MetadataUpdatedMessage
  | MetadataBatchUpdatedMessage
  | PlaylistCreatedMessage
  | PlaylistUpdatedMessage
  | PlaylistDeletedMessage
  | EnhancementSettingsChangedMessage
  | MasteringRecommendationMessage
  | ArtworkUpdatedMessage
  | ScanProgressMessage
  | ScanCompleteMessage;

// ============================================================================
// Type Guards
// ============================================================================

export function isPlayerStateMessage(msg: WebSocketMessage): msg is PlayerStateMessage {
  return msg.type === 'player_state';
}

export function isPlaybackStartedMessage(msg: WebSocketMessage): msg is PlaybackStartedMessage {
  return msg.type === 'playback_started';
}

export function isPlaybackPausedMessage(msg: WebSocketMessage): msg is PlaybackPausedMessage {
  return msg.type === 'playback_paused';
}

export function isMasteringRecommendationMessage(msg: WebSocketMessage): msg is MasteringRecommendationMessage {
  return msg.type === 'mastering_recommendation';
}

export function isEnhancementSettingsChangedMessage(msg: WebSocketMessage): msg is EnhancementSettingsChangedMessage {
  return msg.type === 'enhancement_settings_changed';
}

export function isLibraryUpdatedMessage(msg: WebSocketMessage): msg is LibraryUpdatedMessage {
  return msg.type === 'library_updated';
}

export function isMetadataUpdatedMessage(msg: WebSocketMessage): msg is MetadataUpdatedMessage {
  return msg.type === 'metadata_updated';
}

export function isScanProgressMessage(msg: WebSocketMessage): msg is ScanProgressMessage {
  return msg.type === 'scan_progress';
}

export function isQueueChangedMessage(msg: WebSocketMessage): msg is QueueChangedMessage {
  return msg.type === 'queue_changed';
}

export function isQueueShuffledMessage(msg: WebSocketMessage): msg is QueueShuffledMessage {
  return msg.type === 'queue_shuffled';
}

export function isRepeatModeChangedMessage(msg: WebSocketMessage): msg is RepeatModeChangedMessage {
  return msg.type === 'repeat_mode_changed';
}

// ============================================================================
// Helper Types from Backend
// ============================================================================

export interface TrackInfo {
  id: number;
  title: string;
  artist: string;
  album: string;
  duration: number;
  filepath: string;
  // Additional fields (optional)
  artwork_url?: string;
  genre?: string;
  year?: number;
  bitrate?: number;
  sample_rate?: number;
  bit_depth?: number;
  format?: string;
  loudness?: number;
  crest_factor?: number;
  centroid?: number;
  date_added?: string;
  date_modified?: string;
}

// ============================================================================
// Exports
// ============================================================================

export const ALL_MESSAGE_TYPES: WebSocketMessageType[] = [
  'player_state',
  'playback_started',
  'playback_paused',
  'playback_stopped',
  'track_loaded',
  'track_changed',
  'position_changed',
  'volume_changed',
  'queue_updated',
  'queue_changed',
  'queue_shuffled',
  'repeat_mode_changed',
  'library_updated',
  'metadata_updated',
  'metadata_batch_updated',
  'playlist_created',
  'playlist_updated',
  'playlist_deleted',
  'enhancement_settings_changed',
  'mastering_recommendation',
  'artwork_updated',
  'scan_progress',
  'scan_complete',
];

export const PLAYER_STATE_TYPES: WebSocketMessageType[] = [
  'player_state',
  'playback_started',
  'playback_paused',
  'playback_stopped',
  'track_loaded',
  'track_changed',
  'position_changed',
  'volume_changed',
];

export const QUEUE_TYPES: WebSocketMessageType[] = [
  'queue_updated',
  'queue_changed',
  'queue_shuffled',
  'repeat_mode_changed',
];

export const ENHANCEMENT_TYPES: WebSocketMessageType[] = [
  'enhancement_settings_changed',
  'mastering_recommendation',
];

export const LIBRARY_TYPES: WebSocketMessageType[] = [
  'library_updated',
  'metadata_updated',
  'metadata_batch_updated',
  'scan_progress',
  'scan_complete',
];
