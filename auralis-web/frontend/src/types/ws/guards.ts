/**
 * WebSocket message types — type guards.
 * Split from the former monolithic types/websocket.ts (#4081); consumers import
 * via the '@/types/websocket' barrel.
 *
 * Only the two guards with real consumers live here (#5219): routing is by
 * message-type literal (`subscribe('playback_started', …)`), so a guard per
 * type is scaffolding no call site reaches. A handler that needs narrowing
 * should compare `msg.type` inline rather than add a guard.
 */


import type { WebSocketMessage, WebSocketErrorMessage } from './base';

import type { AnyWebSocketMessage } from './registry';

import type { LibraryTracksRemovedMessage } from './library';


// ============================================================================
// Type Guards
// ============================================================================

// Accepts the full handler union (AnyWebSocketMessage | WebSocketMessage) so
// direct context-subscribe handlers can call it too (#5622) — mirroring
// isWebSocketErrorMessage below. The useWebSocketMessages-only parameter
// (#4197) predates consumers subscribing outside that helper.
export function isLibraryTracksRemovedMessage(
  msg: AnyWebSocketMessage | WebSocketMessage
): msg is LibraryTracksRemovedMessage {
  return msg.type === 'library_tracks_removed';
}

export const isWebSocketErrorMessage = (msg: AnyWebSocketMessage | WebSocketMessage): msg is WebSocketErrorMessage =>
  msg.type === 'error';
