/**
 * useRestAPI Hook
 *
 * Type-safe REST API client hook.
 * Handles request/response, error management, and loading states.
 *
 * Usage:
 *   const api = useRestAPI();
 *   const response = await api.get<PlayerState>('/api/player/status');
 *   await api.post('/api/player/queue', { tracks: ['/music/song.wav'], start_index: 0 });
 */

import { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import type { ApiError } from '@/types/api';
import { ApiErrorHandler } from '@/types/api';
import { API_BASE_URL } from '@/config/api';
import { httpErrorFromResponse } from '@/utils/httpError';
const REQUEST_TIMEOUT = 30000; // 30 seconds

/**
 * Optional runtime shape guard for a parsed response body (#4896).
 *
 * `Response.json()` is `Promise<any>`, so every `as T` in this hook is a
 * compile-time-only contract — backend field drift surfaces as a downstream
 * `undefined`/NaN far from its cause. Mirrors the `validate` option
 * `apiRequest.ts` added for the same reason (#4607): when supplied and the
 * body fails the guard, the request rejects with an error naming the
 * endpoint instead of returning a silently-wrong `T`. Endpoints that don't
 * pass one behave exactly as before.
 *
 * @example
 * const queue = await get('/api/player/queue', { validate: isQueueResponseShape });
 */
export interface ResponseValidationOptions {
  validate?: (value: unknown) => boolean;
}

type QueryParams = Record<string, string | number | boolean>;

/**
 * The only things that differ between the HTTP verbs (#5198). Everything else
 * about a request lives once, in `request()`.
 */
interface RequestSpec {
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  /** JSON body; sent only when truthy. */
  payload?: Record<string, unknown>;
  queryParams?: QueryParams;
  options?: ResponseValidationOptions;
  /** Resolve without reading the response body (DELETE). */
  skipBody?: boolean;
}

/**
 * REST API client hook.
 * Provides type-safe methods for GET, POST, PUT, PATCH, DELETE requests.
 */
export function useRestAPI() {
  // Counter-based loading: each in-flight request increments on entry and decrements
  // in finally. isLoading stays true until all concurrent requests finish (fixes #2489:
  // a shared boolean flag was cleared by the first completing request even when a
  // second was still in-flight).
  const inflightCount = useRef(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  // Track all in-flight AbortControllers so requests can be cancelled on unmount
  // (fixes #2467: no hook-level abort on unmount caused setState on dead state).
  const activeControllers = useRef(new Set<AbortController>());

  // Per-endpoint sequence counters to detect stale responses (fixes #2439, #3055).
  // Scoped per endpoint so concurrent requests to different endpoints don't
  // invalidate each other.
  const requestSequences = useRef(new Map<string, number>());

  useEffect(() => {
    return () => {
      activeControllers.current.forEach((c) => c.abort());
    };
  }, []);

  /**
   * Build full URL from endpoint path with optional query parameters.
   */
  const buildUrl = useCallback((endpoint: string, queryParams?: QueryParams): string => {
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
  }, []);

  /**
   * Generic fetch with timeout.
   */
  const fetchWithTimeout = useCallback(
    async (url: string, options: RequestInit = {}): Promise<Response> => {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);
      activeControllers.current.add(controller);

      try {
        const response = await fetch(url, {
          ...options,
          signal: controller.signal,
        });
        return response;
      } finally {
        clearTimeout(timeoutId);
        activeControllers.current.delete(controller);
      }
    },
    []
  );

  /**
   * The request lifecycle shared by every verb (#5198).
   *
   * Each verb used to hand-copy all of this, so every fix to it (#2439, #2467,
   * #2489, #4831, #4896) had to be applied five times.
   */
  const request = useCallback(
    async <T>(endpoint: string, spec: RequestSpec): Promise<T> => {
      const { method, payload, queryParams, options, skipBody } = spec;
      const seq = (requestSequences.current.get(endpoint) ?? 0) + 1;
      requestSequences.current.set(endpoint, seq);
      inflightCount.current += 1;
      setIsLoading(true);
      setError(null);

      try {
        const url = buildUrl(endpoint, queryParams);
        const response = await fetchWithTimeout(url, {
          method,
          headers: {
            'Content-Type': 'application/json',
          },
          ...(payload ? { body: JSON.stringify(payload) } : {}),
        });

        if (!response.ok) {
          // Read the backend's `detail` before discarding the body (#4831).
          throw await httpErrorFromResponse(response);
        }

        // Detect stale response: if a newer request started after this one, discard this response (fixes #2439).
        if (seq !== requestSequences.current.get(endpoint)) {
          response.body?.cancel();
          throw Object.assign(new Error('Stale response'), { name: 'StaleRequestError' });
        }

        if (skipBody) {
          return undefined as T;
        }

        const data = await response.json();

        // Runtime shape check at the boundary, when the caller supplied one (#4896).
        if (options?.validate && !options.validate(data)) {
          throw new Error(`Unexpected response shape from ${endpoint}`);
        }

        return data as T;
      } catch (err) {
        // AbortError from unmount cleanup or StaleRequestError — don't surface as API error (fixes #2467, #2439)
        if (err instanceof Error && (err.name === 'AbortError' || err.name === 'StaleRequestError')) {
          throw err;
        }
        const apiError = ApiErrorHandler.parse(err);
        setError(apiError);
        throw apiError;
      } finally {
        if ((inflightCount.current -= 1) <= 0) { inflightCount.current = 0; setIsLoading(false); }
      }
    },
    [buildUrl, fetchWithTimeout]
  );

  /**
   * GET request.
   */
  const get = useCallback(
    <T = unknown>(endpoint: string, options?: ResponseValidationOptions): Promise<T> =>
      request<T>(endpoint, { method: 'GET', options }),
    [request]
  );

  /**
   * POST request.
   *
   * `payload` (2nd arg) is the JSON body; `queryParams` (3rd arg) appends to the
   * URL. They are NOT interchangeable — a body is only sent when `payload` is
   * truthy, so passing data as the 3rd argument silently sends no body.
   *
   * Every POST/PUT endpoint on the Auralis backend takes a Pydantic body model
   * (verified across all routers: the only non-body params are path params and
   * file uploads), so `payload` is effectively always what you want. This
   * docblock previously advertised the opposite as "the Auralis backend
   * convention" and cited `/api/player/seek` — which in fact takes a
   * `SeekRequest` body — and that example is what produced #4859.
   *
   * Usage:
   *   await api.post('/api/player/queue/shuffle', { enabled: true });
   */
  const post = useCallback(
    <T = unknown>(endpoint: string, payload?: Record<string, unknown>, queryParams?: QueryParams, options?: ResponseValidationOptions): Promise<T> =>
      request<T>(endpoint, { method: 'POST', payload, queryParams, options }),
    [request]
  );

  /**
   * PUT request.
   * Supports both JSON body and query parameters.
   */
  const put = useCallback(
    <T = unknown>(endpoint: string, payload?: Record<string, unknown>, queryParams?: QueryParams, options?: ResponseValidationOptions): Promise<T> =>
      request<T>(endpoint, { method: 'PUT', payload, queryParams, options }),
    [request]
  );

  /**
   * PATCH request.
   * Supports both JSON body and query parameters.
   */
  const patch = useCallback(
    <T = unknown>(endpoint: string, payload?: Record<string, unknown>, queryParams?: QueryParams, options?: ResponseValidationOptions): Promise<T> =>
      request<T>(endpoint, { method: 'PATCH', payload, queryParams, options }),
    [request]
  );

  /**
   * DELETE request. Resolves without reading the response body.
   */
  const delete_ = useCallback(
    (endpoint: string): Promise<void> => request<void>(endpoint, { method: 'DELETE', skipBody: true }),
    [request]
  );

  /**
   * Clear error state.
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // Memoize only the stable method references — isLoading/error are excluded from
  // deps so that state changes during a request don't recreate the object and
  // trigger downstream effects that depend on the api reference.
  const stableMethods = useMemo(
    () => ({ get, post, put, patch, delete: delete_, clearError }),
    [get, post, put, patch, delete_, clearError]
  );

  return useMemo(
    () => ({ ...stableMethods, isLoading, error }),
    [stableMethods, isLoading, error]
  );
}
