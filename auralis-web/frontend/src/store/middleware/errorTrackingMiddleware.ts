/**
 * Redux Error Tracking Middleware
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Middleware for centralized error tracking and recovery.
 * Monitors Redux actions for errors and provides recovery mechanisms.
 *
 * Features:
 * - Automatic error detection from action payloads
 * - Error categorization and context tracking
 * - Recovery action suggestions
 * - Error analytics collection
 * - Retry with exponential backoff
 * - Error boundary integration
 *
 * Phase C.4d: Redux Error Handling
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import type { Middleware } from '@reduxjs/toolkit';
import * as connectionActions from '@/store/slices/connectionSlice';

// ============================================================================
// Error Types and Interfaces
// ============================================================================

export enum ErrorCategory {
  NETWORK = 'network',
  VALIDATION = 'validation',
  AUTHENTICATION = 'authentication',
  AUTHORIZATION = 'authorization',
  SERVER = 'server',
  CLIENT = 'client',
  UNKNOWN = 'unknown',
}

export interface TrackedError {
  id: string;
  timestamp: number;
  category: ErrorCategory;
  message: string;
  action: string;
  context?: Record<string, unknown>;
  stack?: string;
  retryCount: number;
  maxRetries: number;
}

export interface ErrorTrackingConfig {
  enabled?: boolean;
  maxErrors?: number;
  /**
   * Optional allowlist narrowing which actions may be tracked as errors (#4662).
   *
   * Detection is otherwise a substring heuristic (`payload.error`, or an action
   * type containing `Error`/`Failure`/`setError`), which is deliberately broad.
   * Supplying this restricts tracking to the listed actions *in addition to*
   * that heuristic — it never causes an action the heuristic rejected to be
   * tracked.
   *
   * Each entry matches either the full action type (`'player/setError'`) or the
   * name after the last `/` (`'setError'`).
   *
   * Omitted — the default — means unrestricted. It previously defaulted to
   * `['setError', 'setLastError']`, but that value was never read by anything,
   * so it carried no behaviour; applying it literally would have silently
   * dropped real errors such as `player/setStreamingError`.
   */
  errorActions?: string[];
  onError?: (error: TrackedError) => void;
  logToConsole?: boolean;
  // #4695: `logToServer`, `captureErrorToServer`, `onRecovery` and
  // `recoveryStrategies` were removed here. The first posted to `/api/errors`,
  // a route that has never existed; the other three were declared (and two of
  // them defaulted) but never read by anything. A config field with no
  // implementation is a promise the middleware does not keep — see #4453 for
  // the same defect in `enabled`, and #4662 for `errorActions`.
}

// ============================================================================
// Error Detection and Categorization
// ============================================================================

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
const TRANSPORT_ERROR_ACTIONS: ReadonlySet<string> = new Set([
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
const CONNECTION_RESET_ACTIONS: ReadonlySet<string> = new Set([
  'connection/setWSConnected',
  'connection/setAPIConnected',
]);

/**
 * Detect error type from message
 */
function categorizeError(message: string): ErrorCategory {
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
function generateErrorId(): string {
  // #4623: slice(2, 11), not substr(2, 9) — substr is ES Annex B legacy and
  // takes (start, length) where slice takes (start, end), so the end index is
  // 2 + 9. The 9-character suffix is load-bearing for ID shape.
  return `err_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;
}

// ============================================================================
// Error Tracking Middleware Factory
// ============================================================================

const defaultConfig: ErrorTrackingConfig = {
  enabled: true,
  maxErrors: 50,
  // No `errorActions` default: omitted means unrestricted (#4662). The former
  // `['setError', 'setLastError']` default was never read, so it had no
  // behaviour to preserve — and enforcing it literally would have dropped
  // `player/setStreamingError` and `connection/setConnectionError`, which the
  // heuristic tracks today.
  logToConsole: true,
};

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

/**
 * Error store for tracking
 */
class ErrorStore {
  private errors: Map<string, TrackedError> = new Map();
  private maxErrors: number;

  constructor(maxErrors: number = 50) {
    this.maxErrors = maxErrors;
  }

  add(error: TrackedError): void {
    this.errors.set(error.id, error);

    // Keep bounded
    if (this.errors.size > this.maxErrors) {
      const firstKey = this.errors.keys().next().value;
      if (firstKey !== undefined) {
        this.errors.delete(firstKey);
      }
    }
  }

  get(id: string): TrackedError | undefined {
    return this.errors.get(id);
  }

  getAll(): TrackedError[] {
    return Array.from(this.errors.values());
  }

  getByAction(action: string): TrackedError[] {
    return Array.from(this.errors.values()).filter((e) => e.action === action);
  }

  getByCategory(category: ErrorCategory): TrackedError[] {
    return Array.from(this.errors.values()).filter((e) => e.category === category);
  }

  clear(): void {
    this.errors.clear();
  }

  size(): number {
    return this.errors.size;
  }
}

/**
 * Create Redux error tracking middleware
 */
export function createErrorTrackingMiddleware(
  config: ErrorTrackingConfig = {}
): Middleware {
  const finalConfig: ErrorTrackingConfig = { ...defaultConfig, ...config };
  const errorStore = new ErrorStore(finalConfig.maxErrors);

  return (store) => {
    // #4430: bumped every time the connection is (re)established. A deferred
    // forward captures this at schedule time and bails if it changed, so a
    // setError queued before a reconnect cannot land after it. Per-store
    // (inside this closure) rather than module-level, so parallel test stores
    // don't invalidate each other's forwards.
    let connectionGeneration = 0;

    return (next) => (action: unknown): unknown => {
      // Error tracking disabled — pass the action straight through so nothing
      // is tracked, logged, reported, or recovered (#4453). Previously the
      // `enabled` flag was never read in a conditional, so `{ enabled: false }`
      // silently kept tracking.
      if (!finalConfig.enabled) {
        return next(action);
      }

      // Runtime guards to safely access action properties without Record<string, any> cast (#3044)
      const actionType = (action != null && typeof action === 'object' && 'type' in action && typeof (action as { type: unknown }).type === 'string')
        ? (action as { type: string }).type
        : undefined;
      const actionPayload = (action != null && typeof action === 'object' && 'payload' in action)
        ? (action as { payload: unknown }).payload
        : undefined;

      try {
        const result = next(action);

        // #4430: setWSConnected(true)/setAPIConnected(true) clear
        // connection.lastError synchronously in the reducer. Bump the
        // generation so any forward already queued for a microtask is
        // discarded rather than landing after the reset.
        if (CONNECTION_RESET_ACTIONS.has(actionType ?? '') && actionPayload === true) {
          connectionGeneration++;
        }

        // Check if action contains error
        let shouldTrackError = false;
        let errorMessage: string = 'Unknown error';
        let errorContext: Record<string, unknown> | undefined;

        // Case 1: Object payload with error indicators
        if (actionPayload && typeof actionPayload === 'object') {
          const payload = actionPayload as Record<string, unknown>;

          if (payload.error || actionType?.includes('Error') || actionType?.includes('Failure')) {
            shouldTrackError = true;
            errorMessage = String(payload.error || payload.message || actionType || 'Unknown error');
            errorContext = payload;
          }
        }
        // Case 2: String payload for error actions (e.g., player/setError)
        else if (
          typeof actionPayload === 'string' &&
          (actionType?.includes('Error') || actionType?.includes('Failure') || actionType?.includes('setError'))
        ) {
          shouldTrackError = true;
          errorMessage = actionPayload;
          errorContext = { message: actionPayload };
        }

        // #4662: apply the allowlist, if one was configured. This narrows the
        // heuristic above and never widens it, so an unconfigured middleware
        // behaves exactly as before.
        if (shouldTrackError && !isAllowedErrorAction(actionType, finalConfig.errorActions)) {
          shouldTrackError = false;
        }

        if (shouldTrackError) {
          const trackedError: TrackedError = {
            id: generateErrorId(),
            timestamp: Date.now(),
            category: categorizeError(String(errorMessage)),
            message: String(errorMessage),
            action: actionType ?? 'unknown',
            context: errorContext,
            retryCount: 0,
            maxRetries: 3,
          };

          // Store error
          errorStore.add(trackedError);

          // Log if enabled
          if (finalConfig.logToConsole) {
            console.error(`[Error Tracked] ${trackedError.category}: ${trackedError.message}`, {
              action: actionType,
              context: errorContext,
            });
          }

          // Call error callback (wrap in try-catch to prevent callback errors from cascading)
          try {
            finalConfig.onError?.(trackedError);
          } catch (callbackError) {
            // Silently ignore errors in error callbacks to prevent infinite loops
            if (finalConfig.logToConsole) {
              console.error('[Error Tracking] onError callback threw:', callbackError);
            }
          }

          // Attempt recovery based on category.
          // Defer dispatch to avoid re-entrant dispatch mid-action-processing (#3023).
          //
          // #4430: gated on the originating action, not just the message
          // keywords — a queue/cache/player failure whose text happens to say
          // "timeout" is not a connection problem.
          if (
            trackedError.category === ErrorCategory.NETWORK &&
            TRANSPORT_ERROR_ACTIONS.has(actionType ?? '')
          ) {
            // Network errors - trigger reconnection attempt (deferred).
            // #4430: capture the connection generation so a reconnect that
            // happens between scheduling and flushing discards this forward
            // instead of having a stale error overwrite the cleared state.
            const scheduledGeneration = connectionGeneration;
            Promise.resolve().then(() => {
              if (connectionGeneration !== scheduledGeneration) return;
              store.dispatch(connectionActions.setError(trackedError.message));
            });
          }
        }

        return result;
      } catch (error) {
        // Handle middleware errors
        const errorMessage =
          error instanceof Error ? error.message : String(error);

        const trackedError: TrackedError = {
          id: generateErrorId(),
          timestamp: Date.now(),
          category: categorizeError(errorMessage),
          message: errorMessage,
          action: actionType ?? 'unknown',
          stack: error instanceof Error ? error.stack : undefined,
          retryCount: 0,
          maxRetries: 3,
        };

        errorStore.add(trackedError);

        if (finalConfig.logToConsole) {
          console.error(`[Middleware Error] ${trackedError.category}:`, error);
        }

        // Call error callback (wrap in try-catch to prevent callback errors from cascading)
        try {
          finalConfig.onError?.(trackedError);
        } catch (callbackError) {
          // Silently ignore errors in error callbacks to prevent infinite loops
          if (finalConfig.logToConsole) {
            console.error('[Error Tracking] onError callback threw:', callbackError);
          }
        }

        throw error;
      }
    };
  };
}

// ============================================================================
// Error Recovery Utilities
// ============================================================================

/**
 * Retry an asynchronous executor with exponential backoff.
 *
 * #3241: previously this function took a plain action object and returned it
 * unmodified on the first iteration, so the loop, catch handler, and backoff
 * were all dead code. The signature now takes a callable so the loop has
 * something to invoke; on success the resolved value is returned, on failure
 * the loop waits 2^attempt seconds and tries again until `maxRetries` is
 * exhausted, then rethrows the last captured error.
 */
export async function retryAction<T>(
  executor: () => Promise<T> | T,
  maxRetries: number = 3
): Promise<T> {
  let lastError: Error | undefined;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await executor();
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));

      // Don't sleep after the final attempt — the loop is about to exit.
      if (attempt < maxRetries - 1) {
        const delay = Math.pow(2, attempt) * 1000; // 1s, 2s, 4s, ...
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }
  }

  throw lastError ?? new Error('Max retries exceeded');
}

// ============================================================================
// Error Analytics
// ============================================================================

/**
 * Calculate error statistics
 */
export function getErrorStats(errors: TrackedError[]) {
  return {
    total: errors.length,
    byCategory: Object.values(ErrorCategory).reduce(
      (acc, category) => {
        acc[category] = errors.filter((e) => e.category === category).length;
        return acc;
      },
      {} as Record<string, number>
    ),
    byAction: errors.reduce(
      (acc, error) => {
        acc[error.action] = (acc[error.action] || 0) + 1;
        return acc;
      },
      {} as Record<string, number>
    ),
    recentErrors: errors.slice(-10),
    mostRecentError: errors[errors.length - 1],
  };
}

// ============================================================================
// Exports
// ============================================================================

export { ErrorStore, generateErrorId, categorizeError };
