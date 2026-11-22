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
  generateErrorId,
  isAllowedErrorAction,
} from './errorCategorization';
import { buildTrackedError, detectActionError, notifyOnError, readActionShape } from './errorTrackingHelpers';

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
  // Do not add config fields this middleware does not implement (#4695:
  // `logToServer` posted to /api/errors, a route that never existed; three
  // others were declared and defaulted but never read). A config field with
  // no implementation is a promise the middleware does not keep — see #4453
  // for the same defect in `enabled`, and #4662 for `errorActions`.
}

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

      const shape = readActionShape(action);
      const actionType = shape.type;

      try {
        const result = next(action);

        // #4430: setWSConnected(true)/setAPIConnected(true) clear
        // connection.lastError synchronously in the reducer. Bump the
        // generation so any forward already queued for a microtask is
        // discarded rather than landing after the reset.
        if (CONNECTION_RESET_ACTIONS.has(actionType ?? '') && shape.payload === true) {
          connectionGeneration++;
        }

        // #4662: the allowlist, if configured, narrows the heuristic and never
        // widens it, so an unconfigured middleware behaves exactly as before.
        const detected = detectActionError(shape);
        if (!detected || !isAllowedErrorAction(actionType, finalConfig.errorActions)) {
          return result;
        }

        const trackedError = buildTrackedError(detected.message, actionType, { context: detected.context });
        if (finalConfig.logToConsole) {
          console.error(`[Error Tracked] ${trackedError.category}: ${trackedError.message}`, {
            action: actionType,
            context: detected.context,
          });
        }
        notifyOnError(finalConfig, trackedError);

        // Network errors from a transport action trigger a reconnection
        // attempt. Deferred to avoid re-entrant dispatch mid-action (#3023).
        // #4430: gated on the originating action, not just the message
        // keywords (a queue/cache/player failure whose text says "timeout" is
        // not a connection problem), and on the connection generation captured
        // now, so a reconnect before the flush discards this stale forward.
        if (
          trackedError.category === ErrorCategory.NETWORK &&
          TRANSPORT_ERROR_ACTIONS.has(actionType ?? '')
        ) {
          const scheduledGeneration = connectionGeneration;
          Promise.resolve().then(() => {
            if (connectionGeneration !== scheduledGeneration) return;
            store.dispatch(connectionActions.setError(trackedError.message));
          });
        }

        return result;
      } catch (error) {
        // A reducer or downstream middleware threw: track it, then rethrow.
        const trackedError = buildTrackedError(
          error instanceof Error ? error.message : String(error),
          actionType,
          { stack: error instanceof Error ? error.stack : undefined }
        );
        if (finalConfig.logToConsole) {
          console.error(`[Middleware Error] ${trackedError.category}:`, error);
        }
        notifyOnError(finalConfig, trackedError);
        throw error;
      }
    };
  };
}

// ============================================================================
// Exports
// ============================================================================

// #5213: categorizeError is not re-exported — nothing outside these modules
// imports it, and exporting it implied other code categorized errors the same
// way. buildTrackedError (errorTrackingHelpers.ts) is its one caller.
//
// #5017: this middleware deliberately has no retry/stats/ErrorStore layer.
// Tracked errors are logged and handed to onError at the point of detection;
// anything more needs an external retrieval surface first, not an
// accumulator nothing reads.
