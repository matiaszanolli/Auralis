/**
 * Unregistered-message-type diagnostics for the WebSocket provider.
 *
 * Split out of WebSocketContext.tsx (#5841).
 */

import { ALL_MESSAGE_TYPES } from '@/types/websocket';

// ============================================================================
// Unregistered-type diagnostics (#4617)
// ============================================================================

/** Server→client frames that are deliberately absent from ALL_MESSAGE_TYPES.
 *
 * `audio_chunk_meta` is consumed inside the connection hook and fused with the
 * following binary PCM frame into a synthetic `audio_chunk` (#4167); the
 * keepalive/control frames are handled by the connection layer. None of them is
 * a public subscription key, so none of them is a missing registration. */
const INTERNAL_MESSAGE_TYPES: ReadonlySet<string> = new Set([
  'audio_chunk_meta',
  'ping',
  'pong',
  'heartbeat',
]);

const KNOWN_MESSAGE_TYPES: ReadonlySet<string> = new Set<string>(ALL_MESSAGE_TYPES);

/** Types already warned about — one line per type, not per frame. */
const warnedUnregisteredTypes = new Set<string>();

/**
 * Warn (dev builds only) when a frame arrives whose type is on no registry.
 *
 * A backend broadcast whose literal was never added to `ALL_MESSAGE_TYPES` can
 * have no subscribers by construction: `subscribe()` is typed on
 * `WebSocketMessageType`, so the dispatch map can never hold that key and the
 * frame is dropped without a trace. That is exactly how `cache_cleared` stayed
 * dead from #3545 until #4585 (#4617) — silence made the omission invisible.
 */
export function warnIfUnregisteredType(type: string): void {
  if (!import.meta.env.DEV) return;
  if (KNOWN_MESSAGE_TYPES.has(type) || INTERNAL_MESSAGE_TYPES.has(type)) return;
  if (warnedUnregisteredTypes.has(type)) return;
  warnedUnregisteredTypes.add(type);
  console.warn(
    `[WebSocket] Received unregistered message type "${type}" — it has no entry in ` +
      'ALL_MESSAGE_TYPES, so no subscriber can ever receive it. Add it to types/ws/ ' +
      '(or to INTERNAL_MESSAGE_TYPES if it is deliberately internal).'
  );
}

/** Test seam: clears the once-per-type warning memo. */
export function resetUnregisteredTypeWarnings(): void {
  warnedUnregisteredTypes.clear();
}
