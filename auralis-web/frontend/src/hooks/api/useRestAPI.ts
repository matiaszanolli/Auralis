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

import { useState, useCallback, useMemo, useEffect } from 'react';
import type { ApiResponse, ApiError } from '../../types/api';
import { ApiErrorHandler } from '../../types/api';

// Configuration
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8765';
const REQUEST_TIMEOUT = 30000; // 30 seconds

/**
 * REST API client hook.
 * Provides type-safe methods for GET, POST, PUT, DELETE requests.
 */
export function useRestAPI() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  /**
   * Build full URL from endpoint path.
   */
  const buildUrl = useCallback((endpoint: string): string => {
    if (endpoint.startsWith('http')) {
      return endpoint;
    }
    return `${API_BASE_URL}${endpoint}`;
  }, []);

  /**
   * Generic fetch with timeout.
   */
  const fetchWithTimeout = useCallback(
    async (url: string, options: RequestInit = {}): Promise<Response> => {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

      try {
        const response = await fetch(url, {
          ...options,
          signal: controller.signal,
        });
        return response;
      } finally {
        clearTimeout(timeoutId);
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
   */
  const post = useCallback(
    async <T = any>(endpoint: string, payload?: any): Promise<T> => {
      setIsLoading(true);
      setError(null);

      try {
        const url = buildUrl(endpoint);
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
   */
  const put = useCallback(
    async <T = any>(endpoint: string, payload?: any): Promise<T> => {
      setIsLoading(true);
      setError(null);

      try {
        const url = buildUrl(endpoint);
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
   */
  const patch = useCallback(
    async <T = any>(endpoint: string, payload?: any): Promise<T> => {
      setIsLoading(true);
      setError(null);

      try {
        const url = buildUrl(endpoint);
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

  // Memoize return object to prevent unnecessary re-renders
  return useMemo(
    () => ({
      get,
      post,
      put,
      patch,
      delete: delete_,
      clearError,
      isLoading,
      error,
    }),
    [get, post, put, patch, delete_, clearError, isLoading, error]
  );
}

/**
 * Hook for making a single GET request on mount.
 * Useful for loading initial data.
 */
export function useQuery<T = any>(endpoint: string, skip: boolean = false) {
  const api = useRestAPI();
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(!skip);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    if (skip) return;

    const fetchData = async () => {
      try {
        setIsLoading(true);
        const result = await api.get<T>(endpoint);
        setData(result);
        setError(null);
      } catch (err) {
        setError(api.error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [endpoint, skip, api]);

  return { data, isLoading, error };
}

/**
 * Hook for making a single POST request.
 * Returns a function to trigger the request.
 */
export function useMutation<T = any>(endpoint: string, method: 'POST' | 'PUT' | 'DELETE' = 'POST') {
  const api = useRestAPI();
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const mutate = useCallback(
    async (payload?: any) => {
      try {
        setIsLoading(true);
        let result: T;

        if (method === 'POST') {
          result = await api.post<T>(endpoint, payload);
        } else if (method === 'PUT') {
          result = await api.put<T>(endpoint, payload);
        } else {
          await api.delete(endpoint);
          result = null as T;
        }

        setData(result);
        setError(null);
        return result;
      } catch (err) {
        setError(api.error);
        throw api.error;
      } finally {
        setIsLoading(false);
      }
    },
    [api, endpoint, method]
  );

  return { mutate, data, isLoading, error };
}
