/**
 * WebSocket message types — player domain.
 * Split from the former monolithic types/websocket.ts (#4081); consumers import
 * via the '@/types/websocket' barrel which re-exports every ws/* module.
 */


import type { WebSocketMessage, TrackInfo } from './base';

/** Message-type literals owned by the player domain. */
export type PlayerMessageType =
  | 'player_state'
  | 'playback_started'
  | 'playback_paused'
  | 'playback_resumed'
  | 'playback_stopped'
  | 'track_loaded'
  | 'track_changed'
  | 'position_changed'
  | 'volume_changed'
  | 'seek_started';


// ============================================================================
// Player State Messages
// ============================================================================

/**
 * Raw player state as sent by the backend (snake_case fields).
 * Matches the Pydantic PlayerState model in backend/player_state.py.
 */
export interface RawPlayerStateData {
  // 'error' is declared on the backend enum (PlaybackState.ERROR) but not
  // currently emitted by any production code path; included for forward
  // compatibility so downstream switches narrow correctly (#3546 / BE-NEW-88).
  state: 'playing' | 'paused' | 'stopped' | 'loading' | 'error';
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
  repeat_mode: 'off' | 'all' | 'one';
  mastering_enabled: boolean;
  current_preset: string;
  analysis?: Record<string, unknown> | null;
  // Enhancement/gapless fields (optional — not always present).
  //
  // #3778: the backend `PlayerState` schema does NOT currently emit
  // these fields, so in practice `transformPlayerState` always falls
  // through to the defaults below (gaplessEnabled=true,
  // crossfadeEnabled=true, crossfadeDuration=3.0). Kept as `?` here so
  // the contract can be filled in from the backend side without a
  // breaking client-typing change. If you need to consume these in a
  // component, add the corresponding fields to the backend
  // PlayerState first — relying on the defaults is misleading.
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


export interface PlaybackResumedMessage extends WebSocketMessage {
  type: 'playback_resumed';
  data: {
    state: 'playing';
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
    // 'next' / 'previous' from sequential advance; 'jumped' is emitted by
    // NavigationService.jump_to_track and includes a `track_index` field
    // identifying the new queue position (#3504 / BE-NEW-46).
    action: 'next' | 'previous' | 'jumped';
    track_index?: number;
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


/** Sent by system.py seek handler to acknowledge a seek request */
export interface SeekStartedMessage extends WebSocketMessage {
  type: 'seek_started';
  data: {
    position: number; // Seconds
    /** Track this seek targeted — lets the client ignore stale seek
     *  acks after a track change (#3547 / BE-NEW-89). */
    track_id?: number;
  };
}
