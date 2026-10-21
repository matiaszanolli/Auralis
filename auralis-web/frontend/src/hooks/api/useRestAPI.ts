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
import { APIRequestError } from '@/utils/apiRequest';
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
 * A type predicate tied to the call's `T` (#5637), matching `apiRequest`'s
 * option: a guard asserting a different shape than the call declares doesn't
 * compile, and a passing guard narrows the parsed body so the verb returns
 * it without the unchecked `as T`.
 *
 * @example
 * const queue = await get('/api/player/queue', { validate: isQueueResponseShape });
 */
export interface ResponseValidationOptions<T = unknown> {
  validate?: (value: unknown) => value is T;
}

// null/undefined entries are allowed and skipped by buildUrl's guard — the
// hook's own contract, exercised by useRestAPI.test's param filtering test
// (#5640). Entries with a value must be primitive.
type QueryParams = Record<string, string | number | boolean | null | undefined>;

/**
 * The only things that differ between the HTTP verbs (#5198). Everything else
 * about a request lives once, in `request()`.
 */
interface RequestSpec<T = unknown> {
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  /** JSON body; sent only when truthy. */
  payload?: Record<string, unknown>;
  queryParams?: QueryParams;
  options?: ResponseValidationOptions<T>;
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

  // GET-only stale-response detection (#2439, #3055; narrowed to GET by
  // #5608). Keyed on method + full URL, so two GETs that differ only by
  // query string don't cancel each other. Mutations are never discarded —
  // their server-side effect has already happened by the time the response
  // arrives.
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
      // didTimeout distinguishes OUR timeout from an unmount/supersession
      // abort: both reject fetch with the same AbortError, but a timeout must
      // surface as an error (#5609) — callers treat AbortError as a silent
      // cancel, which left timed-out library queries rendering empty with no
      // error. Mirrors utils/apiRequest.ts's identical mapping (#5019).
      let didTimeout = false;
      const timeoutId = setTimeout(() => {
        didTimeout = true;
        controller.abort();
      }, REQUEST_TIMEOUT);
      activeControllers.current.add(controller);

      try {
        const response = await fetch(url, {
          ...options,
          signal: controller.signal,
        });
        return response;
      } catch (err) {
        if (didTimeout) {
          throw new APIRequestError(`Request timed out after ${REQUEST_TIMEOUT}ms`, 0);
        }
        throw err;
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
    async <T>(endpoint: string, spec: RequestSpec<T>): Promise<T> => {
      const { method, payload, queryParams, options, skipBody } = spec;
      const url = buildUrl(endpoint, queryParams);

      // Stale-response detection is a GET-only concern (#2439): a newer GET
      // to the same URL supersedes the older in-flight response. When the
      // verbs merged into this shared lifecycle (#5198), the guard silently
      // started covering mutations too — a second POST to the same endpoint
      // made the first throw "Stale response" even though the server had
      // already applied it (#5608). Key on the full URL (query string
      // included), not the bare endpoint.
      let seq: number | undefined;
      if (method === 'GET') {
        seq = (requestSequences.current.get(url) ?? 0) + 1;
        requestSequences.current.set(url, seq);
      }

      inflightCount.current += 1;
      setIsLoading(true);
      setError(null);

      try {
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

        // Detect stale response: if a newer GET started after this one, discard
        // this response (fixes #2439). Mutations never take this branch (#5608).
        if (seq !== undefined && seq !== requestSequences.current.get(url)) {
          response.body?.cancel();
          throw Object.assign(new Error('Stale response'), { name: 'StaleRequestError' });
        }

        if (skipBody) {
          return undefined as T;
        }

        const data: unknown = await response.json();

        // Runtime shape check at the boundary, when the caller supplied one (#4896).
        // A predicate guard narrows the body to the call's `T` — no cast (#5637).
        if (options?.validate) {
          if (!options.validate(data)) {
            throw new Error(`Unexpected response shape from ${endpoint}`);
          }
          return data;
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
    <T = unknown>(endpoint: string, options?: ResponseValidationOptions<T>): Promise<T> =>
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
    <T = unknown>(endpoint: string, payload?: Record<string, unknown>, queryParams?: QueryParams, options?: ResponseValidationOptions<T>): Promise<T> =>
      request<T>(endpoint, { method: 'POST', payload, queryParams, options }),
    [request]
  );

  /**
   * PUT request.
   * Supports both JSON body and query parameters.
   */
  const put = useCallback(
    <T = unknown>(endpoint: string, payload?: Record<string, unknown>, queryParams?: QueryParams, options?: ResponseValidationOptions<T>): Promise<T> =>
      request<T>(endpoint, { method: 'PUT', payload, queryParams, options }),
    [request]
  );

  /**
   * PATCH request.
   * Supports both JSON body and query parameters.
   */
  const patch = useCallback(
    <T = unknown>(endpoint: string, payload?: Record<string, unknown>, queryParams?: QueryParams, options?: ResponseValidationOptions<T>): Promise<T> =>
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
