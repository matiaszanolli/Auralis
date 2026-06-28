/**
 * WebSocket message types — registry (composed unions + message-type tables).
 * Split from the former monolithic types/websocket.ts (#4081); consumers import
 * via the '@/types/websocket' barrel.
 */


import type { WebSocketErrorMessage } from './base';

import type {
  PlayerMessageType,
  PlayerStateMessage,
  PlaybackStartedMessage,
  PlaybackPausedMessage,
  PlaybackResumedMessage,
  PlaybackStoppedMessage,
  TrackLoadedMessage,
  TrackChangedMessage,
  PositionChangedMessage,
  VolumeChangedMessage,
  SeekStartedMessage,
} from './player';

import type {
  QueueMessageType,
  QueueUpdatedMessage,
  QueueChangedMessage,
  QueueShuffledMessage,
  RepeatModeChangedMessage,
} from './queue';

import type {
  LibraryMessageType,
  LibraryUpdatedMessage,
  MetadataUpdatedMessage,
  MetadataBatchUpdatedMessage,
  PlaylistCreatedMessage,
  PlaylistUpdatedMessage,
  PlaylistDeletedMessage,
  ScanProgressMessage,
  ScanCompleteMessage,
  LibraryScanStartedMessage,
  LibraryScanErrorMessage,
  LibraryTracksRemovedMessage,
} from './library';

import type {
  StreamingMessageType,
  AudioStreamStartMessage,
  AudioStreamEndMessage,
  AudioChunkMessage,
  AudioStreamErrorMessage,
} from './streaming';
// Note: AudioChunkMetaMessage is intentionally NOT imported here — it is an
// internal type consumed by WebSocketContext and is not part of the public
// AnyWebSocketMessage union / ALL_MESSAGE_TYPES (#4167).

import type {
  EnhancementMessageType,
  EnhancementSettingsChangedMessage,
  MasteringRecommendationMessage,
  ArtworkUpdatedMessage,
  FingerprintProgressMessage,
} from './enhancement';

/** All WebSocket message-type literals (union of the per-domain literal types). */
export type WebSocketMessageType =
  | PlayerMessageType
  | QueueMessageType
  | LibraryMessageType
  | StreamingMessageType
  | EnhancementMessageType
  | 'error';


// ============================================================================
// Union Type for All Messages
// ============================================================================

export type AnyWebSocketMessage =
  | PlayerStateMessage
  | PlaybackStartedMessage
  | PlaybackPausedMessage
  | PlaybackResumedMessage
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
  | LibraryScanErrorMessage
  | LibraryTracksRemovedMessage
  | WebSocketErrorMessage;


// ============================================================================
// Exports
// ============================================================================

export const ALL_MESSAGE_TYPES: readonly WebSocketMessageType[] = [
  'player_state',
  'playback_started',
  'playback_paused',
  'playback_resumed',
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
  'fingerprint_progress',
  'seek_started',
  'audio_stream_start',
  'audio_stream_end',
  'audio_chunk',
  'audio_stream_error',
  'scan_progress',
  'scan_complete',
  'library_scan_started',
  'library_scan_error',
  'library_tracks_removed',
  'error',
] as const satisfies readonly WebSocketMessageType[];


// Compile-time exhaustiveness check: fails to compile if a
// WebSocketMessageType value is missing from ALL_MESSAGE_TYPES.
type _AssertExhaustive = WebSocketMessageType extends
  (typeof ALL_MESSAGE_TYPES)[number] ? true : never;

const _exhaustiveCheck: _AssertExhaustive = true;
void _exhaustiveCheck;


export const PLAYER_STATE_TYPES: WebSocketMessageType[] = [
  'player_state',
  'playback_started',
  'playback_paused',
  'playback_resumed',
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
  'library_scan_error',
  'library_tracks_removed',
];
