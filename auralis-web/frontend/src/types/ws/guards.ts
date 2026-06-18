/**
 * WebSocket message types — type guards.
 * Split from the former monolithic types/websocket.ts (#4081); consumers import
 * via the '@/types/websocket' barrel.
 */


import { makeGuard } from './base';

import type { WebSocketMessage, WebSocketErrorMessage } from './base';

import type { AnyWebSocketMessage } from './registry';

import type {
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
  QueueUpdatedMessage,
  QueueChangedMessage,
  QueueShuffledMessage,
  RepeatModeChangedMessage,
} from './queue';

import type {
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
  AudioStreamStartMessage,
  AudioStreamEndMessage,
  AudioChunkMessage,
  AudioStreamErrorMessage,
} from './streaming';

import type {
  EnhancementSettingsChangedMessage,
  MasteringRecommendationMessage,
  ArtworkUpdatedMessage,
  FingerprintProgressMessage,
} from './enhancement';


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


export function isPlaybackResumedMessage(msg: WebSocketMessage): msg is PlaybackResumedMessage {
  return msg.type === 'playback_resumed';
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

// Library-scan guards mirror isScanProgressMessage's WebSocketMessage signature
// (not makeGuard's stricter AnyWebSocketMessage) so they accept the
// WebSocketMessage handed to useWebSocketSubscription callbacks (#4197).
export function isLibraryScanStartedMessage(msg: WebSocketMessage): msg is LibraryScanStartedMessage {
  return msg.type === 'library_scan_started';
}

export function isLibraryScanErrorMessage(msg: WebSocketMessage): msg is LibraryScanErrorMessage {
  return msg.type === 'library_scan_error';
}

export function isLibraryTracksRemovedMessage(msg: WebSocketMessage): msg is LibraryTracksRemovedMessage {
  return msg.type === 'library_tracks_removed';
}

export const isWebSocketErrorMessage = (msg: AnyWebSocketMessage | WebSocketMessage): msg is WebSocketErrorMessage =>
  msg.type === 'error';
