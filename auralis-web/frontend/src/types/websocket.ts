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
  // Fingerprint messages (fixes #2282)
  | 'fingerprint_progress'
  // Seek acknowledgement (fixes #2282)
  | 'seek_started'
  // Audio stream lifecycle messages (fixes #2282)
  | 'audio_stream_start'
  | 'audio_stream_end'
  | 'audio_chunk'
  | 'audio_stream_error'
  // System messages
  | 'scan_progress'
  | 'scan_complete'
  | 'library_scan_started'
  | 'library_tracks_removed';

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
 * Raw player state as sent by the backend (snake_case fields).
 * Matches the Pydantic PlayerState model in backend/player_state.py.
 */
export interface RawPlayerStateData {
  state: string;
  is_playing: boolean;
  is_paused: boolean;
  current_track: TrackInfo | null;
  current_time: number;
  duration: number;
  volume: number; // 0-100 integer scale
  is_muted: boolean;
  queue: TrackInfo[];
  queue_index: number;
  queue_size: number;
  shuffle_enabled: boolean;
  repeat_mode: string;
  mastering_enabled: boolean;
  current_preset: string;
  analysis?: Record<string, unknown> | null;
  // Enhancement/gapless fields (optional — not always present)
  gapless_enabled?: boolean;
  crossfade_enabled?: boolean;
  crossfade_duration?: number;
}

/**
 * Frontend-facing camelCase representation of player state.
 * Use transformPlayerState() to convert from RawPlayerStateData.
 */
export interface PlayerStateData {
  currentTrack: TrackInfo | null;
  isPlaying: boolean;
  volume: number; // 0-100 integer scale (matches backend default of 80)
  position: number; // Seconds
  duration: number; // Seconds
  queue: TrackInfo[];
  queueIndex: number;
  gaplessEnabled: boolean;
  crossfadeEnabled: boolean;
  crossfadeDuration: number; // Seconds
}

/**
 * Transform raw backend snake_case player state to frontend camelCase.
 */
export function transformPlayerState(raw: RawPlayerStateData): PlayerStateData {
  return {
    currentTrack: raw.current_track ?? null,
    isPlaying: raw.is_playing ?? false,
    volume: raw.volume ?? 80,
    position: raw.current_time ?? 0,
    duration: raw.duration ?? 0,
    queue: raw.queue ?? [],
    queueIndex: raw.queue_index ?? -1,
    gaplessEnabled: raw.gapless_enabled ?? true,
    crossfadeEnabled: raw.crossfade_enabled ?? true,
    crossfadeDuration: raw.crossfade_duration ?? 3.0,
  };
}

export interface PlayerStateMessage extends WebSocketMessage {
  type: 'player_state';
  data: RawPlayerStateData;
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
    volume: number; // 0-100 integer scale (matches PlayerState.volume sent by backend)
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
// Fingerprint Messages (fixes #2282)
// ============================================================================

/** Sent by audio_stream_controller.py while computing track fingerprint (fixes #2502) */
export interface FingerprintProgressMessage extends WebSocketMessage {
  type: 'fingerprint_progress';
  data: {
    track_id: number;
    status: 'analyzing' | 'complete' | 'failed' | 'error' | 'cached' | 'queued';
    message: string;
    stream_type?: 'enhanced' | 'normal';
  };
}

/** Sent by system.py seek handler to acknowledge a seek request */
export interface SeekStartedMessage extends WebSocketMessage {
  type: 'seek_started';
  data: {
    position: number; // Seconds
  };
}

// ============================================================================
// Audio Stream Messages (fixes #2282)
// ============================================================================

/** Sent when a new audio stream begins (fixes #2503) */
export interface AudioStreamStartMessage extends WebSocketMessage {
  type: 'audio_stream_start';
  data: {
    track_id: number;
    preset: string;
    intensity: number;
    sample_rate: number;
    channels: number;
    total_chunks: number;
    chunk_duration: number;
    total_duration: number;
    stream_type?: 'enhanced' | 'normal';
    is_seek?: boolean;
    start_chunk?: number;
    seek_position?: number;
    seek_offset?: number;
  };
}

export interface AudioStreamEndMessage extends WebSocketMessage {
  type: 'audio_stream_end';
  data: {
    track_id: number;
  };
}

/** Sent for each PCM audio chunk during streaming (fixes #2501) */
export interface AudioChunkMessage extends WebSocketMessage {
  type: 'audio_chunk';
  data: {
    chunk_index: number;
    chunk_count: number;
    frame_index: number;
    frame_count: number;
    samples: string; // base64-encoded float32 PCM
    sample_count: number;
    crossfade_samples: number;
    stream_type?: 'enhanced' | 'normal';
  };
}

export interface AudioStreamErrorMessage extends WebSocketMessage {
  type: 'audio_stream_error';
  data: {
    track_id: number;
    error: string;
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
    files_added: number;
    duration: number; // Seconds
  };
}

export interface LibraryScanStartedMessage extends WebSocketMessage {
  type: 'library_scan_started';
  data: {
    directories: string[];
  };
}

export interface LibraryTracksRemovedMessage extends WebSocketMessage {
  type: 'library_tracks_removed';
  data: {
    count: number;
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
  | FingerprintProgressMessage
  | SeekStartedMessage
  | AudioStreamStartMessage
  | AudioStreamEndMessage
  | AudioChunkMessage
  | AudioStreamErrorMessage
  | ScanProgressMessage
  | ScanCompleteMessage
  | LibraryScanStartedMessage
  | LibraryTracksRemovedMessage;

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
// Generated type guards for the remaining 19 message types (#2548)
// Uses a factory so each guard is a single, consistent, type-safe expression.
// ============================================================================

function makeGuard<T extends AnyWebSocketMessage>(type: T['type']) {
  return (msg: AnyWebSocketMessage): msg is T => msg.type === type;
}

export const isPlaybackStoppedMessage       = makeGuard<PlaybackStoppedMessage>('playback_stopped');
export const isTrackLoadedMessage           = makeGuard<TrackLoadedMessage>('track_loaded');
export const isTrackChangedMessage          = makeGuard<TrackChangedMessage>('track_changed');
export const isPositionChangedMessage       = makeGuard<PositionChangedMessage>('position_changed');
export const isVolumeChangedMessage         = makeGuard<VolumeChangedMessage>('volume_changed');
export const isQueueUpdatedMessage          = makeGuard<QueueUpdatedMessage>('queue_updated');
export const isMetadataBatchUpdatedMessage  = makeGuard<MetadataBatchUpdatedMessage>('metadata_batch_updated');
export const isPlaylistCreatedMessage       = makeGuard<PlaylistCreatedMessage>('playlist_created');
export const isPlaylistUpdatedMessage       = makeGuard<PlaylistUpdatedMessage>('playlist_updated');
export const isPlaylistDeletedMessage       = makeGuard<PlaylistDeletedMessage>('playlist_deleted');
export const isArtworkUpdatedMessage        = makeGuard<ArtworkUpdatedMessage>('artwork_updated');
export const isFingerprintProgressMessage   = makeGuard<FingerprintProgressMessage>('fingerprint_progress');
export const isSeekStartedMessage           = makeGuard<SeekStartedMessage>('seek_started');
export const isAudioStreamStartMessage      = makeGuard<AudioStreamStartMessage>('audio_stream_start');
export const isAudioStreamEndMessage        = makeGuard<AudioStreamEndMessage>('audio_stream_end');
export const isAudioChunkMessage            = makeGuard<AudioChunkMessage>('audio_chunk');
export const isAudioStreamErrorMessage      = makeGuard<AudioStreamErrorMessage>('audio_stream_error');
export const isScanCompleteMessage          = makeGuard<ScanCompleteMessage>('scan_complete');

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
  'library_scan_started',
  'library_tracks_removed',
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
  'library_scan_started',
  'library_tracks_removed',
];
