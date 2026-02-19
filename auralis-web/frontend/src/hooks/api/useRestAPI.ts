/**
 * useRestAPI Hook
 *
 * Type-safe REST API client hook.
 * Handles request/response, error management, and loading states.
 *
 * Usage:
 *   const api = useRestAPI();
 *   const response = await api.get<PlayerState>('/api/player/state');
 *   await api.post('/api/player/play', { track_path: '/music/song.wav' });
 */

import { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import type { ApiResponse, ApiError } from '../../types/api';
import { ApiErrorHandler } from '../../types/api';

// Configuration
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8765';
const REQUEST_TIMEOUT = 30000; // 30 seconds

/**
 * REST API client hook.
 * Provides type-safe methods for GET, POST, PUT, DELETE requests.
 */
export function useRestAPI() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  // Track all in-flight AbortControllers so requests can be cancelled on unmount
  // (fixes #2467: no hook-level abort on unmount caused setState on dead state).
  const activeControllers = useRef(new Set<AbortController>());

  useEffect(() => {
    return () => {
      activeControllers.current.forEach((c) => c.abort());
    };
  }, []);

  /**
   * Build full URL from endpoint path with optional query parameters.
   */
  const buildUrl = useCallback((endpoint: string, queryParams?: Record<string, any>): string => {
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
   * GET request.
   */
  const get = useCallback(
    async <T = any>(endpoint: string): Promise<T> => {
      setIsLoading(true);
      setError(null);

      try {
        const url = buildUrl(endpoint);
        const response = await fetchWithTimeout(url, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        return data as T;
      } catch (err) {
        // AbortError from unmount cleanup — don't surface as API error (fixes #2467)
        if (err instanceof Error && err.name === 'AbortError') {
          throw err;
        }
        const apiError = ApiErrorHandler.parse(err);
        setError(apiError);
        throw apiError;
      } finally {
        setIsLoading(false);
      }
    },
    [buildUrl, fetchWithTimeout]
  );

  /**
   * POST request.
   * Supports both JSON body (for GET-like data) and query parameters (for Auralis backend).
   *
   * Usage:
   *   // JSON body (legacy)
   *   await api.post('/api/queue', { tracks: [1, 2, 3] });
   *
   *   // Query parameters (Auralis backend)
   *   await api.post('/api/player/seek', undefined, { position: 120 });
   */
  const post = useCallback(
    async <T = any>(endpoint: string, payload?: any, queryParams?: Record<string, any>): Promise<T> => {
      setIsLoading(true);
      setError(null);

      try {
        const url = buildUrl(endpoint, queryParams);
        const response = await fetchWithTimeout(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: payload ? JSON.stringify(payload) : undefined,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        return data as T;
      } catch (err) {
        // AbortError from unmount cleanup — don't surface as API error (fixes #2467)
        if (err instanceof Error && err.name === 'AbortError') {
          throw err;
        }
        const apiError = ApiErrorHandler.parse(err);
        setError(apiError);
        throw apiError;
      } finally {
        setIsLoading(false);
      }
    },
    [buildUrl, fetchWithTimeout]
  );

  /**
   * PUT request.
   * Supports both JSON body and query parameters.
   */
  const put = useCallback(
    async <T = any>(endpoint: string, payload?: any, queryParams?: Record<string, any>): Promise<T> => {
      setIsLoading(true);
      setError(null);

      try {
        const url = buildUrl(endpoint, queryParams);
        const response = await fetchWithTimeout(url, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: payload ? JSON.stringify(payload) : undefined,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        return data as T;
      } catch (err) {
        // AbortError from unmount cleanup — don't surface as API error (fixes #2467)
        if (err instanceof Error && err.name === 'AbortError') {
          throw err;
        }
        const apiError = ApiErrorHandler.parse(err);
        setError(apiError);
        throw apiError;
      } finally {
        setIsLoading(false);
      }
    },
    [buildUrl, fetchWithTimeout]
  );

  /**
   * PATCH request.
   * Supports both JSON body and query parameters.
   */
  const patch = useCallback(
    async <T = any>(endpoint: string, payload?: any, queryParams?: Record<string, any>): Promise<T> => {
      setIsLoading(true);
      setError(null);

      try {
        const url = buildUrl(endpoint, queryParams);
        const response = await fetchWithTimeout(url, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
          },
          body: payload ? JSON.stringify(payload) : undefined,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        return data as T;
      } catch (err) {
        // AbortError from unmount cleanup — don't surface as API error (fixes #2467)
        if (err instanceof Error && err.name === 'AbortError') {
          throw err;
        }
        const apiError = ApiErrorHandler.parse(err);
        setError(apiError);
        throw apiError;
      } finally {
        setIsLoading(false);
      }
    },
    [buildUrl, fetchWithTimeout]
  );

  /**
   * DELETE request.
   */
  const delete_ = useCallback(
    async (endpoint: string): Promise<void> => {
      setIsLoading(true);
      setError(null);

      try {
        const url = buildUrl(endpoint);
        const response = await fetchWithTimeout(url, {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json',
          },
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
      } catch (err) {
        // AbortError from unmount cleanup — don't surface as API error (fixes #2467)
        if (err instanceof Error && err.name === 'AbortError') {
          throw err;
        }
        const apiError = ApiErrorHandler.parse(err);
        setError(apiError);
        throw apiError;
      } finally {
        setIsLoading(false);
      }
    },
    [buildUrl, fetchWithTimeout]
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

  return { ...stableMethods, isLoading, error };
}

/**
 * Hook for making a single GET request on mount.
 * Useful for loading initial data.
 */
export function useQuery<T = any>(endpoint: string, skip: boolean = false) {
  const { get } = useRestAPI();
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(!skip);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    if (skip) return;

    const fetchData = async () => {
      try {
        setIsLoading(true);
        const result = await get<T>(endpoint);
        setData(result);
        setError(null);
      } catch (err) {
        setError(err as ApiError);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [endpoint, skip, get]);

  return { data, isLoading, error };
}

/**
 * Hook for making a single POST request.
 * Returns a function to trigger the request.
 */
export function useMutation<T = any>(endpoint: string, method: 'POST' | 'PUT' | 'DELETE' = 'POST') {
  const { post, put, delete: apiDelete } = useRestAPI();
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const mutate = useCallback(
    async (payload?: any) => {
      try {
        setIsLoading(true);
        let result: T;

        if (method === 'POST') {
          result = await post<T>(endpoint, payload);
        } else if (method === 'PUT') {
          result = await put<T>(endpoint, payload);
        } else {
          await apiDelete(endpoint);
          result = null as T;
        }

        setData(result);
        setError(null);
        return result;
      } catch (err) {
        const apiError = err as ApiError;
        setError(apiError);
        throw apiError;
      } finally {
        setIsLoading(false);
      }
    },
    [post, put, apiDelete, endpoint, method]
  );

  return { mutate, data, isLoading, error };
}
