/**
 * WebSocket message types — system domain.
 *
 * Backend-wide events that don't belong to the player/queue/library/streaming/
 * enhancement domains. Consumers import via the '@/types/websocket' barrel
 * which re-exports every ws/* module.
 */


import type { WebSocketMessage } from './base';

/** Message-type literals owned by the system domain. */
export type SystemMessageType = 'cache_cleared';


// ============================================================================
// System Messages
// ============================================================================

/**
 * Broadcast by `POST /api/cache/clear` after both cache tiers are dropped
 * (`routers/cache_streamlined.py`).
 *
 * #4585: this type existed on the wire but had no frontend counterpart, so
 * `WebSocketContext.dispatchMessage` resolved it to an empty handler set and
 * discarded it silently. It is the unfinished half of #3545 — that issue
 * flagged both the missing `{type, data}` envelope (fixed) and the missing
 * `WebSocketMessageType` registration (this).
 */
export interface CacheClearedMessage extends WebSocketMessage {
  type: 'cache_cleared';
  data: {
    message: string;
  };
}
