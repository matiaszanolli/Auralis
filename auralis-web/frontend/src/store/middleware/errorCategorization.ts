/**
 * Error categorization for the error-tracking middleware.
 *
 * Split out of errorTrackingMiddleware.ts (#5841): the category enum, the
 * message heuristic, the transport/connection-reset action sets, error-id
 * generation and the `errorActions` allowlist check. The middleware factory
 * re-exports the public names, so existing imports are unchanged.
 */

export enum ErrorCategory {
  NETWORK = 'network',
  VALIDATION = 'validation',
  AUTHENTICATION = 'authentication',
  AUTHORIZATION = 'authorization',
  SERVER = 'server',
  CLIENT = 'client',
  UNKNOWN = 'unknown',
}

/**
 * Action types whose NETWORK-categorized errors genuinely describe the
 * client↔server transport, and therefore belong in `connection.lastError`
 * (#4430).
 *
 * `categorizeError` inspects the message text alone, so a queue, cache or
 * player failure whose message merely *contains* "timeout"/"connection" was
 * previously forwarded here and surfaced through `useAppErrors` /
 * `useConnectionHealth` as though the socket were down. Origin decides, not
 * wording.
 *
 * `connection/*` is deliberately absent: those actions already write connection
 * state directly, so forwarding them would be redundant and re-entrant. That
 * exclusion used to be the *only* gate.
 */
export const TRANSPORT_ERROR_ACTIONS: ReadonlySet<string> = new Set([
  // The WebSocket audio stream — the one non-connection slice that reports real
  // transport failures (useAudioStreamingCore / useEnhancedStreamStart /
  // useEnhancedPlayCommand dispatch this when the socket drops or the stream
  // aborts mid-playback).
  'player/setStreamingError',
]);

/**
 * Connection actions that synchronously clear `connection.lastError`.
 * Used to invalidate a deferred forward that would otherwise land after a
 * reconnect and resurrect a stale error (#4430).
 */
export const CONNECTION_RESET_ACTIONS: ReadonlySet<string> = new Set([
  'connection/setWSConnected',
  'connection/setAPIConnected',
]);

/**
 * Detect error type from message
 */
export function categorizeError(message: string): ErrorCategory {
  const lowerMessage = message.toLowerCase();

  if (
    lowerMessage.includes('network') ||
    lowerMessage.includes('connection') ||
    lowerMessage.includes('offline') ||
    lowerMessage.includes('timeout')
  ) {
    return ErrorCategory.NETWORK;
  }

  if (
    lowerMessage.includes('invalid') ||
    lowerMessage.includes('required') ||
    lowerMessage.includes('format')
  ) {
    return ErrorCategory.VALIDATION;
  }

  if (
    lowerMessage.includes('unauthorized') ||
    lowerMessage.includes('401') ||
    lowerMessage.includes('token')
  ) {
    return ErrorCategory.AUTHENTICATION;
  }

  if (
    lowerMessage.includes('forbidden') ||
    lowerMessage.includes('403') ||
    lowerMessage.includes('permission')
  ) {
    return ErrorCategory.AUTHORIZATION;
  }

  if (
    lowerMessage.includes('500') ||
    lowerMessage.includes('503') ||
    lowerMessage.includes('server')
  ) {
    return ErrorCategory.SERVER;
  }

  if (
    lowerMessage.includes('null') ||
    lowerMessage.includes('undefined') ||
    lowerMessage.includes('syntax')
  ) {
    return ErrorCategory.CLIENT;
  }

  return ErrorCategory.UNKNOWN;
}

/**
 * Generate unique error ID
 */
export function generateErrorId(): string {
  // #4623: slice(2, 11), not substr(2, 9) — substr is ES Annex B legacy and
  // takes (start, length) where slice takes (start, end), so the end index is
  // 2 + 9. The 9-character suffix is load-bearing for ID shape.
  return `err_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;
}

/**
 * Whether `actionType` is permitted by an `errorActions` allowlist.
 *
 * An absent or empty list means unrestricted, so the middleware's default
 * behaviour is exactly the heuristic on its own.
 */
export function isAllowedErrorAction(
  actionType: string | undefined,
  errorActions: string[] | undefined
): boolean {
  if (!errorActions || errorActions.length === 0) return true;
  if (!actionType) return false;

  const actionName = actionType.slice(actionType.lastIndexOf('/') + 1);
  return errorActions.some((allowed) => allowed === actionType || allowed === actionName);
}
