/**
 * WebSocket message types — system domain.
 *
 * Backend-wide events that don't belong to the player/queue/library/streaming/
 * enhancement domains. Consumers import via the '@/types/websocket' barrel
 * which re-exports every ws/* module.
 */


import type { WebSocketMessage } from './base';

/** Message-type literals owned by the system domain. */
export type SystemMessageType =
  | 'cache_cleared'
  | 'job_progress';


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


/**
 * Per-tick progress for one background processing job.
 *
 * Emitted by `ws_handlers/messages.py::handle_subscribe_job_progress` to the
 * connections that sent a `subscribe_job_progress` frame for that `job_id`;
 * the backend has declared it as `WebSocketMessageType.JOB_PROGRESS` in
 * `schemas.py` since it was written.
 *
 * #4680: it had no frontend counterpart at all. The only thing that ever read
 * it was a raw string compare in `services/processingService.ts`, which
 * bypassed this registry entirely and has since been deleted — so the type was
 * emitted, undeclared, and unconsumed. Declaring it is what makes a
 * type-safe subscriber possible; there is no subscriber yet, and one should
 * arrive with whatever UI next surfaces job progress.
 */
export interface JobProgressMessage extends WebSocketMessage {
  type: 'job_progress';
  data: {
    job_id: string;
    /** 0.0-1.0. */
    progress: number;
    message: string;
  };
}
