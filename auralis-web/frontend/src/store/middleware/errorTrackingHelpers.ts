/**
 * Error Tracking Helpers
 * ~~~~~~~~~~~~~~~~~~~~~~
 *
 * The pure steps of `createErrorTrackingMiddleware` (#6702): reading an
 * unknown action's shape, deciding whether it carries an error, building the
 * `TrackedError`, and handing it to `onError` without letting a throwing
 * callback escape.
 *
 * @copyright (C) 2024 Auralis Team
 * @license AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
 */

import type { ErrorTrackingConfig, TrackedError } from './errorTrackingMiddleware';
import { categorizeError, generateErrorId } from './errorCategorization';

export interface ActionShape {
  type: string | undefined;
  payload: unknown;
}

export interface DetectedError {
  message: string;
  context: Record<string, unknown>;
}

/** Runtime guards to read an action's type and payload without a Record<string, any> cast (#3044). */
export function readActionShape(action: unknown): ActionShape {
  if (action == null || typeof action !== 'object') {
    return { type: undefined, payload: undefined };
  }
  const type = 'type' in action && typeof (action as { type: unknown }).type === 'string'
    ? (action as { type: string }).type
    : undefined;
  const payload = 'payload' in action ? (action as { payload: unknown }).payload : undefined;
  return { type, payload };
}

/**
 * The error an action carries, by the middleware's substring heuristic, or null.
 *
 * An object payload counts when it has `error` or the type says Error/Failure;
 * a string payload counts when the type says Error/Failure/setError
 * (e.g. `player/setError`).
 */
export function detectActionError({ type, payload }: ActionShape): DetectedError | null {
  const errorType = type?.includes('Error') || type?.includes('Failure');
  if (payload && typeof payload === 'object') {
    const fields = payload as Record<string, unknown>;
    if (!fields.error && !errorType) return null;
    return { message: String(fields.error || fields.message || type || 'Unknown error'), context: fields };
  }
  if (typeof payload === 'string' && (errorType || type?.includes('setError'))) {
    return { message: payload, context: { message: payload } };
  }
  return null;
}

export function buildTrackedError(
  message: string,
  actionType: string | undefined,
  extra: Pick<TrackedError, 'context' | 'stack'> = {}
): TrackedError {
  return {
    id: generateErrorId(),
    timestamp: Date.now(),
    category: categorizeError(message),
    message,
    action: actionType ?? 'unknown',
    ...extra,
    retryCount: 0,
    maxRetries: 3,
  };
}

/** Call `onError`, swallowing (and optionally logging) a throw so it cannot cascade or loop. */
export function notifyOnError(config: ErrorTrackingConfig, trackedError: TrackedError): void {
  try {
    config.onError?.(trackedError);
  } catch (callbackError) {
    if (config.logToConsole) {
      console.error('[Error Tracking] onError callback threw:', callbackError);
    }
  }
}
