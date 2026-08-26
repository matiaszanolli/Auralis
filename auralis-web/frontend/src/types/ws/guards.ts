/**
 * WebSocket message types — type guards.
 * Split from the former monolithic types/websocket.ts (#4081); consumers import
 * via the '@/types/websocket' barrel.
 *
 * #5219: the ~29 per-message-type guards that used to live here were deleted.
 * The frontend never dispatched through them — WebSocketContext routes by
 * message-type literal (`subscribe('playback_started', …)`), so a guard per
 * type was scaffolding that no call site ever reached. Only the two guards
 * with real consumers remain; a handler that needs narrowing should compare
 * `msg.type` inline rather than reviving the factory.
 */


import type { WebSocketMessage, WebSocketErrorMessage } from './base';

import type { AnyWebSocketMessage } from './registry';

import type { LibraryTracksRemovedMessage } from './library';


// ============================================================================
// Type Guards
// ============================================================================

// Mirrors WebSocketMessage (not the stricter AnyWebSocketMessage) so it accepts
// the WebSocketMessage handed to useWebSocketMessages callbacks (#4197).
export function isLibraryTracksRemovedMessage(msg: WebSocketMessage): msg is LibraryTracksRemovedMessage {
  return msg.type === 'library_tracks_removed';
}

export const isWebSocketErrorMessage = (msg: AnyWebSocketMessage | WebSocketMessage): msg is WebSocketErrorMessage =>
  msg.type === 'error';
