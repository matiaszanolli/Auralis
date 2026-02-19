/**
 * API Request Utility
 *
 * Centralized fetch wrapper that handles:
 * - Consistent error handling across all services
 * - Error message extraction from response
 * - Standard request headers
 * - Request/response logging
 */

import { getApiUrl } from '../config/api';

export interface APIError {
  message: string;
  detail?: string;
  statusCode: number;
}

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
export async function apiRequest<T = any>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const url = getApiUrl(endpoint);
  const { body, headers = {}, ...fetchOptions } = options;

  // Prepare request headers
  const requestHeaders: HeadersInit = {
    'Content-Type': 'application/json',
    ...headers,
  };

  // Prepare request body
  const fetchBody = body ? JSON.stringify(body) : undefined;

  try {
    const response = await fetch(url, {
      ...fetchOptions,
      headers: requestHeaders,
      body: fetchBody,
    });

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
export async function get<T = any>(endpoint: string, options?: RequestOptions): Promise<T> {
  return apiRequest<T>(endpoint, { ...options, method: 'GET' });
}

/**
 * Make a POST request
 * @example await post('/playlists', { name: 'My Playlist' });
 */
export async function post<T = any>(
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
export async function put<T = any>(
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
export async function patch<T = any>(
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
export async function del<T = any>(endpoint: string, options?: RequestOptions): Promise<T> {
  return apiRequest<T>(endpoint, { ...options, method: 'DELETE' });
}

/**
 * Make a GET request and return the raw Blob response (for file downloads).
 * Throws APIRequestError on non-OK responses.
 * @example const blob = await getBlob('/api/processing/job/123/download');
 */
export async function getBlob(endpoint: string, options?: Omit<RequestOptions, 'body'>): Promise<Blob> {
  const url = getApiUrl(endpoint);
  const { headers = {}, ...fetchOptions } = options ?? {};

  try {
    const response = await fetch(url, {
      ...fetchOptions,
      method: 'GET',
      headers: { ...headers },
    });

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
