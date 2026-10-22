/**
 * URL building and the timeout-bounded fetch used by useRestAPI.
 *
 * Split out of useRestAPI.ts (#5841): both are independent of React state.
 */

import { API_BASE_URL } from '@/config/api';
import { APIRequestError, DEFAULT_TIMEOUT_MS } from '@/utils/apiRequest';

// null/undefined entries are allowed and skipped by buildUrl's guard — the
// hook's own contract, exercised by useRestAPI.test's param filtering test
// (#5640). Entries with a value must be primitive.
export type QueryParams = Record<string, string | number | boolean | null | undefined>;

/**
 * Build full URL from endpoint path with optional query parameters.
 */
export function buildUrl(endpoint: string, queryParams?: QueryParams): string {
  let url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`;

  if (queryParams && Object.keys(queryParams).length > 0) {
    const params = new URLSearchParams();
    Object.entries(queryParams).forEach(([key, value]) => {
      if (value !== null && value !== undefined) {
        params.append(key, String(value));
      }
    });
    url += `?${params.toString()}`;
  }

  return url;
}

/**
 * Generic fetch with timeout.
 */
export async function fetchWithTimeout(
  activeControllers: Set<AbortController>,
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const controller = new AbortController();
  // didTimeout distinguishes OUR timeout from an unmount/supersession
  // abort: both reject fetch with the same AbortError, but a timeout must
  // surface as an error (#5609) — callers treat AbortError as a silent
  // cancel, which left timed-out library queries rendering empty with no
  // error. Mirrors utils/apiRequest.ts's identical mapping (#5019).
  let didTimeout = false;
  const timeoutId = setTimeout(() => {
    didTimeout = true;
    controller.abort();
  }, DEFAULT_TIMEOUT_MS);
  activeControllers.add(controller);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    return response;
  } catch (err) {
    if (didTimeout) {
      throw new APIRequestError(`Request timed out after ${DEFAULT_TIMEOUT_MS}ms`, 0);
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
    activeControllers.delete(controller);
  }
}
