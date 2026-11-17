/**
 * Retry a request a few times when it failed in a way that can clear on its own (#5655).
 *
 * The app seeds its enhancement settings and queue from one GET at startup, and the backend is often
 * still coming up when the window opens. A single failed read used to leave the defaults in place
 * until a reload, with nothing to retry it. Only failures `isRetryableError` calls transient
 * (transport errors, 408/429, 5xx) are repeated; a 4xx, a drifted response shape or an abort is
 * rethrown at once.
 *
 * @module utils/retryTransient
 */

import { isRetryableError } from '@/utils/queryRetry';

/** Waits before each retry: three attempts in all, about 1.3 s of patience. */
export const INITIAL_FETCH_RETRY_DELAYS_MS: readonly number[] = [300, 1000];

export async function retryTransient<T>(
  attempt: () => Promise<T>,
  {
    delaysMs = INITIAL_FETCH_RETRY_DELAYS_MS,
    isCancelled = () => false,
  }: { delaysMs?: readonly number[]; isCancelled?: () => boolean } = {},
): Promise<T> {
  for (let retry = 0; ; retry += 1) {
    try {
      return await attempt();
    } catch (error) {
      const delay = delaysMs[retry];
      if (delay === undefined || isCancelled() || !(error instanceof Error) || !isRetryableError(error)) {
        throw error;
      }
      await new Promise((resolve) => setTimeout(resolve, delay));
      if (isCancelled()) throw error;
    }
  }
}
