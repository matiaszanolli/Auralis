/**
 * Redux Error Tracking Middleware
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Middleware for centralized error tracking. Monitors Redux actions for
 * errors, categorises them, and hands them to `onError`/`logToConsole`.
 *
 * Features:
 * - Automatic error detection from action payloads
 * - Error categorization and context tracking
 * - Optional `errorActions` allowlist restricting which action types are
 *   tracked (#4662)
 *
 * Not provided: recovery action suggestions (there is no recovery mechanism
 * here — a caller that wants one has to build it) and error-boundary
 * integration (the app's ErrorBoundary components do not use this module;
 * `store/index.ts`'s `createErrorTrackingMiddleware` call is its only
 * consumer). Tracked errors are logged (`logToConsole`) and handed to
 * `onError` at the point of detection.
 *
 * Phase C.4d: Redux Error Handling
 *
 * @copyright (C) 2024 Auralis Team
 * @license AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
 */

import type { Middleware } from '@reduxjs/toolkit';
import * as connectionActions from '@/store/slices/connectionSlice';
import {
  CONNECTION_RESET_ACTIONS,
  ErrorCategory,
  TRANSPORT_ERROR_ACTIONS,
  categorizeError,
  generateErrorId,
  isAllowedErrorAction,
} from './errorCategorization';

export { ErrorCategory, generateErrorId, isAllowedErrorAction };

// ============================================================================
// Error Types and Interfaces
// ============================================================================


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


// ============================================================================
// Error Tracking Middleware Factory
// ============================================================================

const defaultConfig: ErrorTrackingConfig = {
  enabled: true,
  // No `errorActions` default: omitted means unrestricted (#4662). The former
  // `['setError', 'setLastError']` default was never read, so it had no
  // behaviour to preserve — and enforcing it literally would have dropped
  // `player/setStreamingError` and `connection/setConnectionError`, which the
  // heuristic tracks today.
  logToConsole: true,
};


/**
 * Create Redux error tracking middleware
 */
export function createErrorTrackingMiddleware(
  config: ErrorTrackingConfig = {}
): Middleware {
  const finalConfig: ErrorTrackingConfig = { ...defaultConfig, ...config };

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
// Exports
// ============================================================================

// #5213: categorizeError dropped from this list — nothing outside this module
// imported it, and exporting it implied other code categorized errors the same
// way. It stays a module-private function, still called at the two dispatch
// sites above.
//
// #5017: retryAction, getErrorStats and the ErrorStore class (plus its two
// `.add()` call sites above) were deleted here — a real retry helper, a
// stats calculator, and an in-memory accumulator with no callers outside
// tests and no way for an external caller to even retrieve the ErrorStore
// instance. Tracked errors are still logged and handed to onError at the
// point of detection; only the unread accumulation was removed.
