/**
 * React Query retry policy.
 *
 * Split out of errorHandling.ts (#5841). Used by App.tsx's QueryClient; React
 * Query applies exponential backoff between the retries shouldRetryQuery
 * allows.
 */

import { APIRequestError } from '@/utils/apiRequest';
import { toError } from '@/utils/errorGuards';

/**
 * Determine if an error is retryable.
 *
 * #4467: this used to substring-match `error.message` for `network`, `503`,
 * `502`, `429` and so on. That retried a non-transient 4xx whose detail text
 * happened to contain one of those digit strings, and could not retry a
 * transient failure whose text lacked the hardcoded words. Errors from
 * `apiRequest` carry the real HTTP status, so eligibility now comes from that:
 *
 * - `0`   — apiRequest's code for a transport failure before any response
 *           (timeout or network error): retryable.
 * - `408` / `429` — request timeout / rate limited: retryable.
 * - `5xx` — server-side, except `501 Not Implemented`, which will not change
 *           on a retry.
 * - anything else, including a 200 that failed the response-shape check:
 *           not retryable.
 *
 * Only an error that did not come through apiRequest — and so has no status —
 * falls back to message wording, restricted to transport-failure words.
 */
export function isRetryableError(error: Error): boolean {
  if (error instanceof APIRequestError) {
    const status = error.statusCode;
    if (status === 0 || status === 408 || status === 429) return true;
    return status >= 500 && status !== 501;
  }

  const message = error.message.toLowerCase();
  return ['network', 'timeout', 'timed out', 'connection', 'econnrefused', 'failed to fetch']
    .some((pattern) => message.includes(pattern));
}

// #5388: no severity/logger layer here — errors are reported through
// console + toasts, not a logger store. Do not add one without a consumer.

/** Retries React Query allows after the first failure (#5387). */
export const MAX_QUERY_RETRIES = 1;

/**
 * React Query `retry` callback (#5387): retry at most MAX_QUERY_RETRIES
 * times, and only errors isRetryableError accepts. A 404/400 fails at once
 * instead of costing a second identical round trip.
 */
export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  return failureCount < MAX_QUERY_RETRIES && isRetryableError(toError(error));
}
