/**
 * API Request Utility — the app's HTTP transport
 *
 * Centralized fetch wrapper that handles:
 * - Consistent error handling across all services
 * - Error message extraction from response
 * - Standard request headers
 * - Timeout via AbortController, with a caller signal forwarded alongside
 * - Optional runtime shape validation at the boundary (`validate`, #4607)
 *
 * ## Target end state (#4693)
 *
 * This module is the single transport. The app used to have three parallel
 * implementations of timeout, retry and error normalisation, which is why
 * #4442 was resolved by *synchronising a constant across all three* rather
 * than by converging them — and why #4467 (retry eligibility matched on error
 * message substrings instead of status codes) would otherwise need fixing in
 * three places.
 *
 * The standardized client is retired (#4693): its cache telemetry types
 * and shape guards survive as `services/api/cacheShapeGuards.ts`, and its
 * two endpoints come through here.
 *
 * The former duplicate is gone (#6216): `hooks/api/useRestAPI.ts` keeps only
 * its React surface — loading/error state, per-hook AbortControllers,
 * stale-request filtering — as a thin wrapper over the `fetchWithTimeout` /
 * `buildUrl` exported here, holding no fetch logic of its own.
 * `restApiTransport.ts` (its private copy of the transport) is deleted.
 *
 * Do not add a third transport. New endpoints go through this module, or
 * through `useRestAPI` when a component needs the React state surface.
 */

import { getApiUrl } from '@/config/api';
import { readHttpErrorBody } from '@/utils/httpError';
import { DEFAULT_TIMEOUT_MS, APIRequestError, type RequestOptions } from './apiRequestTypes';

export { DEFAULT_TIMEOUT_MS, APIRequestError, type RequestOptions } from './apiRequestTypes';

// null/undefined entries are skipped — the useRestAPI param-filtering
// contract (#5640). Values must be primitive.
export type QueryParams = Record<string, string | number | boolean | null | undefined>;

/**
 * Absolute-URL passthrough, otherwise getApiUrl (slash-normalising
 * API_BASE_URL join). Query params are appended in insertion order — the
 * single URL builder for both apiRequest's `params` option and useRestAPI's
 * queryParams (#6216; replaces restApiTransport.buildUrl).
 */
export function buildUrl(endpoint: string, queryParams?: QueryParams): string {
  let url = endpoint.startsWith('http') ? endpoint : getApiUrl(endpoint);
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
 * fetch() wrapper that aborts after `timeoutMs` and composes an internal
 * timeout AbortController with any caller-supplied signal (#4442). Mirrors the
 * pattern in the retired standardized client so all HTTP layers behave the same.
 *
 * On timeout it throws an {@link APIRequestError} (status 0); a caller-triggered
 * abort propagates as the underlying AbortError for the caller-visible catch.
 */
export async function fetchWithTimeout(
  url: string,
  init: RequestInit,
  timeoutMs: number,
  callerSignal?: AbortSignal
): Promise<Response> {
  // timeoutMs <= 0 disables the internal timeout; still forward the caller signal.
  if (timeoutMs <= 0) {
    return fetch(url, { ...init, signal: callerSignal ?? init.signal });
  }

  const controller = new AbortController();
  let didTimeout = false;
  const timeoutId = setTimeout(() => {
    didTimeout = true;
    controller.abort();
  }, timeoutMs);

  // Forward a caller-supplied signal (e.g. unmount cancellation) to the internal
  // controller so either source can abort the in-flight request.
  const onExternalAbort = () => controller.abort();
  if (callerSignal?.aborted) {
    controller.abort();
  } else {
    callerSignal?.addEventListener('abort', onExternalAbort, { once: true });
  }

  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } catch (error) {
    if (didTimeout) {
      throw new APIRequestError(`Request timed out after ${timeoutMs}ms`, 0);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
    callerSignal?.removeEventListener('abort', onExternalAbort);
  }
}

/**
 * Make an API request with consistent error handling
 *
 * @param endpoint API endpoint (e.g., '/playlists', '/player/queue')
 * @param options Fetch options (method, headers, body, etc.)
 * @returns Parsed JSON response
 * @throws APIRequestError on network or API errors
 *
 * @example
 * const playlists = await apiRequest('/playlists');
 * await apiRequest('/playlists/1', { method: 'DELETE' });
 */
export async function apiRequest<T = unknown>(
  endpoint: string,
  options: RequestOptions<T> = {}
): Promise<T> {
  const url = getApiUrl(endpoint);
  const { body, headers = {}, signal, timeoutMs = DEFAULT_TIMEOUT_MS, validate, ...fetchOptions } = options;

  // Prepare request headers
  const requestHeaders: HeadersInit = {
    'Content-Type': 'application/json',
    ...headers,
  };

  // Prepare request body
  const fetchBody = body ? JSON.stringify(body) : undefined;

  try {
    const response = await fetchWithTimeout(
      url,
      {
        ...fetchOptions,
        headers: requestHeaders,
        body: fetchBody,
      },
      timeoutMs,
      signal
    );

    // Handle successful responses
    if (response.ok) {
      // Some endpoints return 204 No Content
      if (response.status === 204) {
        // No body to check — the guard must not run here (#4607).
        return undefined as T;
      }

      const parsed: unknown = await response.json();

      // Runtime shape check at the boundary, when the caller supplied one.
      // Turns silent field drift into a loud, located failure (#4607).
      if (validate) {
        if (!validate(parsed)) {
          throw new APIRequestError(
            `Unexpected response shape from ${endpoint}`,
            response.status,
            'The server response did not match the expected shape. This usually ' +
              'means the backend contract changed and the frontend types are stale.'
          );
        }
        // The guard's predicate narrows the body to the call's `T` — no cast
        // needed (#5637).
        return parsed;
      }

      // No guard: the compile-time-only contract pre-dating #4607. The `as T`
      // here is exactly what a `validate` guard is the antidote for.
      return parsed as T;
    }

    // Handle error responses
    const { detail: errorDetail, parsed } = await readHttpErrorBody(response);
    const errorMessage = errorDetail
      ?? (parsed ? `Request failed with status ${response.status}` : `${response.status} ${response.statusText}`);

    throw new APIRequestError(errorMessage, response.status, errorDetail);
  } catch (error) {
    // Network error or parsing error
    if (error instanceof APIRequestError) {
      throw error;
    }

    const message = error instanceof Error ? error.message : 'Unknown error';
    throw new APIRequestError(`Network error: ${message}`, 0, message);
  }
}

/**
 * Make a GET request
 * @example const data = await get('/playlists');
 */
export async function get<T = unknown>(endpoint: string, options?: RequestOptions<T>): Promise<T> {
  return apiRequest<T>(endpoint, { ...options, method: 'GET' });
}

/**
 * GET that resolves `null` when the endpoint answers 404, rejects otherwise.
 *
 * The "404 means not-ready/absent, everything else is an error" pattern was
 * copy-pasted per hook (#4847 fixed the track copy, #5122 the album copy a
 * month later — the copies had diverged). One expected-non-error status is a
 * transport concern, so the mapping lives here (#6221): a fetcher is now a
 * one-liner and cannot drift back to swallowing 5xx/network errors into
 * `null`.
 *
 * @example const fp = await getOrNullOn404<TrackFingerprintResponse>(`/api/tracks/${id}/fingerprint`);
 */
export async function getOrNullOn404<T>(
  endpoint: string,
  options?: RequestOptions<T>
): Promise<T | null> {
  try {
    return await get<T>(endpoint, options);
  } catch (err) {
    if (err instanceof APIRequestError && err.statusCode === 404) {
      return null;
    }
    throw err;
  }
}

/**
 * Make a POST request
 * @example await post('/playlists', { name: 'My Playlist' });
 */
export async function post<T = unknown>(
  endpoint: string,
  body?: Record<string, any>,
  options?: RequestOptions<T>
): Promise<T> {
  return apiRequest<T>(endpoint, { ...options, method: 'POST', body });
}

/**
 * Make a PUT request
 * @example await put('/playlists/1', { name: 'Updated' });
 */
export async function put<T = unknown>(
  endpoint: string,
  body?: Record<string, any>,
  options?: RequestOptions<T>
): Promise<T> {
  return apiRequest<T>(endpoint, { ...options, method: 'PUT', body });
}

/**
 * Make a PATCH request
 * @example await patch('/playlists/1', { name: 'Updated' });
 */
export async function patch<T = unknown>(
  endpoint: string,
  body?: Record<string, any>,
  options?: RequestOptions<T>
): Promise<T> {
  return apiRequest<T>(endpoint, { ...options, method: 'PATCH', body });
}

/**
 * Make a DELETE request
 * @example await del('/playlists/1');
 */
export async function del<T = unknown>(endpoint: string, options?: RequestOptions<T>): Promise<T> {
  return apiRequest<T>(endpoint, { ...options, method: 'DELETE' });
}
