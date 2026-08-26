/**
 * WebSocket message types — base primitives domain.
 * Split from the former monolithic types/websocket.ts (#4081); consumers import
 * via the '@/types/websocket' barrel which re-exports every ws/* module.
 */


import type { WebSocketMessageType } from './registry';


// ============================================================================
// Base Message Interface
// ============================================================================

export interface WebSocketMessage<T = unknown> {
  type: WebSocketMessageType;
  data: T;
  timestamp?: number;
}


/**
 * WebSocket error message sent by backend security layer (#2874).
 *
 * Note: Does NOT extend WebSocketMessage because the backend schema uses
 * top-level `error`/`message` fields instead of a `data` wrapper.
 */
export interface WebSocketErrorMessage {
  type: 'error';
  error: string;   // e.g. "rate_limit_exceeded", "validation_error"
  message: string;  // Human-readable description
  timestamp?: string;
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
  /**
   * #3634: backend's player_state TrackInfo declares filepath as
   * Field(exclude=True), so WS-sourced queue entries don't have it.
   *
   * #4586: REST endpoints don't return it either — `serialize_track()` defers
   * to `Track.to_dict()`, which omits `filepath` — so this is effectively
   * never populated. #3205 made that deliberate (no server-path leakage).
   * Use `format` for format-aware logic rather than parsing this.
   */
  filepath?: string;
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

