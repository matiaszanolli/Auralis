/**
 * API Request Utility
 *
 * Centralized fetch wrapper that handles:
 * - Consistent error handling across all services
 * - Error message extraction from response
 * - Standard request headers
 * - Request/response logging
 */

import { getApiUrl } from '@/config/api';

/**
 * Default request timeout (ms). Matches the 30s timeout already used by the
 * app's other two HTTP layers (hooks/api/useRestAPI.ts and
 * services/api/standardizedAPIClient.ts) so all three behave the same (#4442).
 */
export const DEFAULT_TIMEOUT_MS = 30000;

export class APIRequestError extends Error {
  constructor(
    message: string,
    public statusCode: number,
    public detail?: string
  ) {
    super(message);
    this.name = 'APIRequestError';
  }
}

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: Record<string, any>;
  /**
   * AbortSignal for cancelling in-flight requests (e.g. on component unmount).
   *
   * @example
   * const controller = new AbortController();
   * get('/api/library/tracks', { signal: controller.signal });
   * // On cleanup:
   * controller.abort();
   */
  signal?: AbortSignal;

  /**
   * Per-request timeout in milliseconds. Defaults to {@link DEFAULT_TIMEOUT_MS}.
   * The internal timeout composes with any caller-supplied `signal` — whichever
   * aborts first wins. Pass `0` to disable the internal timeout.
   */
  timeoutMs?: number;
}

/**
 * fetch() wrapper that aborts after `timeoutMs` and composes an internal
 * timeout AbortController with any caller-supplied signal (#4442). Mirrors the
 * pattern in standardizedAPIClient so all HTTP layers behave the same.
 *
 * On timeout it throws an {@link APIRequestError} (status 0); a caller-triggered
 * abort propagates as the underlying AbortError for the caller-visible catch.
 */
async function fetchWithTimeout(
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
  options: RequestOptions = {}
): Promise<T> {
  const url = getApiUrl(endpoint);
  const { body, headers = {}, signal, timeoutMs = DEFAULT_TIMEOUT_MS, ...fetchOptions } = options;

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
        return undefined as T;
      }
      return response.json();
    }

    // Handle error responses
    let errorMessage = `Request failed with status ${response.status}`;
    let errorDetail: string | undefined;

    try {
      const errorData = await response.json();
      errorDetail = errorData.detail || errorData.message;
      if (errorDetail) {
        errorMessage = errorDetail;
      }
    } catch {
      // Response wasn't JSON, use status text
      errorMessage = `${response.status} ${response.statusText}`;
    }

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
export async function get<T = unknown>(endpoint: string, options?: RequestOptions): Promise<T> {
  return apiRequest<T>(endpoint, { ...options, method: 'GET' });
}

/**
 * Make a POST request
 * @example await post('/playlists', { name: 'My Playlist' });
 */
export async function post<T = unknown>(
  endpoint: string,
  body?: Record<string, any>,
  options?: RequestOptions
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
  options?: RequestOptions
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
  options?: RequestOptions
): Promise<T> {
  return apiRequest<T>(endpoint, { ...options, method: 'PATCH', body });
}

/**
 * Make a DELETE request
 * @example await del('/playlists/1');
 */
export async function del<T = unknown>(endpoint: string, options?: RequestOptions): Promise<T> {
  return apiRequest<T>(endpoint, { ...options, method: 'DELETE' });
}

/**
 * Make a GET request and return the raw Blob response (for file downloads).
 * Throws APIRequestError on non-OK responses.
 * @example const blob = await getBlob('/api/processing/job/123/download');
 */
export async function getBlob(endpoint: string, options?: Omit<RequestOptions, 'body'>): Promise<Blob> {
  const url = getApiUrl(endpoint);
  const { headers = {}, signal, timeoutMs = DEFAULT_TIMEOUT_MS, ...fetchOptions } = options ?? {};

  try {
    const response = await fetchWithTimeout(
      url,
      {
        ...fetchOptions,
        method: 'GET',
        headers: { ...headers },
      },
      timeoutMs,
      signal
    );

    if (response.ok) {
      return response.blob();
    }

    let errorMessage = `Request failed with status ${response.status}`;
    let errorDetail: string | undefined;
    try {
      const errorData = await response.json();
      errorDetail = errorData.detail || errorData.message;
      if (errorDetail) errorMessage = errorDetail;
    } catch {
      errorMessage = `${response.status} ${response.statusText}`;
    }
    throw new APIRequestError(errorMessage, response.status, errorDetail);
  } catch (error) {
    if (error instanceof APIRequestError) throw error;
    const message = error instanceof Error ? error.message : 'Unknown error';
    throw new APIRequestError(`Network error: ${message}`, 0, message);
  }
}
