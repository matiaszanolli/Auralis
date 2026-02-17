/**
 * Standardized API Client
 * ~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Type-safe API client for communicating with Phase B standardized endpoints.
 * Handles request/response validation, caching, and error handling.
 *
 * Phase C.1: Frontend Integration
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { z } from 'zod';

// ============================================================================
// API Response Types (matching backend schemas)
// ============================================================================

/**
 * Standard success response from API
 */
export interface SuccessResponse<T> {
  status: 'success';
  data: T;
  message?: string;
  timestamp: string;
  cache_source?: 'tier1' | 'tier2' | 'miss';
  processing_time_ms?: number;
}

/**
 * Standard error response from API
 */
export interface ErrorResponse {
  status: 'error';
  error: string;
  message: string;
  details?: Record<string, any>;
  timestamp: string;
}

/**
 * Pagination metadata
 */
export interface PaginationMeta {
  limit: number;
  offset: number;
  total: number;
  remaining: number;
  has_more: boolean;
}

/**
 * Paginated response
 */
export interface PaginatedResponse<T> extends SuccessResponse<T[]> {
  pagination: PaginationMeta;
}

/**
 * Cache statistics response
 */
export interface CacheStats {
  tier1: {
    chunks: number;
    size_mb: number;
    hits: number;
    misses: number;
    hit_rate: number;
  };
  tier2: {
    chunks: number;
    size_mb: number;
    hits: number;
    misses: number;
    hit_rate: number;
  };
  overall: {
    total_chunks: number;
    total_size_mb: number;
    total_hits: number;
    total_misses: number;
    overall_hit_rate: number;
    tracks_cached: number;
  };
  tracks: Record<string, {
    track_id: number;
    completion_percent: number;
    fully_cached: boolean;
  }>;
}

/**
 * Cache health response
 */
export interface CacheHealth {
  healthy: boolean;
  tier1_size_mb: number;
  tier1_healthy: boolean;
  tier2_size_mb: number;
  tier2_healthy: boolean;
  total_size_mb: number;
  memory_healthy: boolean;
  tier1_hit_rate: number;
  overall_hit_rate: number;
  timestamp: string;
}

/**
 * Batch operation item
 */
export interface BatchItem {
  id: string;
  action: string;
  data?: Record<string, any>;
}

/**
 * Batch operation request
 */
export interface BatchRequest {
  items: BatchItem[];
  atomic: boolean;
}

/**
 * Batch operation result
 */
export interface BatchItemResult {
  id: string;
  status: 'success' | 'error';
  message?: string;
  error?: string;
}

/**
 * Batch operation response
 */
export interface BatchResponse extends SuccessResponse<BatchItemResult[]> {
  successful: number;
  failed: number;
}

// ============================================================================
// API Client Configuration
// ============================================================================

export interface APIClientConfig {
  baseURL: string;
  timeout?: number;
  retryAttempts?: number;
  retryDelay?: number;
  cacheResponses?: boolean;
  cacheTTL?: number;
  maxCacheSize?: number;
}

/**
 * API Request options
 */
export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  body?: Record<string, any>;
  headers?: Record<string, string>;
  timeout?: number;
  cache?: boolean;
  cacheTTL?: number;
}

/**
 * Type guard for success responses
 */
export function isSuccessResponse<T>(response: any): response is SuccessResponse<T> {
  return !!(response && response.status === 'success' && response.data !== undefined);
}

/**
 * Type guard for error responses
 */
export function isErrorResponse(response: any): response is ErrorResponse {
  return !!(response && response.status === 'error' && response.error !== undefined);
}

/**
 * Type guard for paginated responses
 */
export function isPaginatedResponse<T>(response: any): response is PaginatedResponse<T> {
  return (
    isSuccessResponse(response) &&
    Array.isArray(response.data) &&
    response.pagination !== undefined
  );
}

// ============================================================================
// Standardized API Client
// ============================================================================

export class StandardizedAPIClient {
  private baseURL: string;
  private timeout: number;
  private retryAttempts: number;
  private retryDelay: number;
  private responseCache: Map<string, { data: any; timestamp: number }>;
  private cacheTTL: number;
  private maxCacheSize: number;

  constructor(config: APIClientConfig) {
    this.baseURL = config.baseURL;
    this.timeout = config.timeout ?? 30000;
    this.retryAttempts = config.retryAttempts ?? 3;
    this.retryDelay = config.retryDelay ?? 1000;
    this.cacheTTL = config.cacheTTL ?? 60000; // 60 second default
    this.maxCacheSize = config.maxCacheSize ?? 200;
    this.responseCache = new Map();
  }

  /**
   * Perform an API request with automatic retry and caching
   */
  private async request<T>(
    endpoint: string,
    options: RequestOptions = {}
  ): Promise<SuccessResponse<T> | ErrorResponse> {
    const url = `${this.baseURL}${endpoint}`;
    const method = options.method ?? 'GET';
    const timeout = options.timeout ?? this.timeout;
    const shouldCache = options.cache ?? true;

    // Check cache for GET requests
    if (method === 'GET' && shouldCache) {
      const cachedResponse = this.responseCache.get(url);
      if (cachedResponse) {
        const elapsed = Date.now() - cachedResponse.timestamp;
        if (elapsed < (options.cacheTTL ?? this.cacheTTL)) {
          console.debug(`[API Cache HIT] ${endpoint}`);
          return cachedResponse.data;
        }
        // Stale entry — remove eagerly so it doesn't occupy a slot
        this.responseCache.delete(url);
      }
    }

    let lastError: Error | null = null;

    // Retry logic
    for (let attempt = 0; attempt <= this.retryAttempts; attempt++) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);

        const response = await fetch(url, {
          method,
          headers: {
            'Content-Type': 'application/json',
            ...options.headers
          },
          body: options.body ? JSON.stringify(options.body) : undefined,
          signal: controller.signal
        });

        clearTimeout(timeoutId);

        const data = await response.json();

        // Cache successful responses with LRU eviction
        if (method === 'GET' && shouldCache && response.ok) {
          // Evict oldest entry (Map preserves insertion order) when at capacity
          if (this.responseCache.size >= this.maxCacheSize) {
            const oldestKey = this.responseCache.keys().next().value;
            if (oldestKey !== undefined) {
              this.responseCache.delete(oldestKey);
            }
          }
          this.responseCache.set(url, {
            data,
            timestamp: Date.now()
          });
          console.debug(`[API Cache SET] ${endpoint}`);
        }

        if (!response.ok) {
          console.error(`[API Error] ${method} ${endpoint}: ${response.status}`, data);
          return data as ErrorResponse;
        }

        return data as SuccessResponse<T>;

      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error));

        if (attempt < this.retryAttempts) {
          const delay = this.retryDelay * Math.pow(2, attempt); // Exponential backoff
          console.warn(`[API Retry] ${endpoint} (attempt ${attempt + 1}/${this.retryAttempts}) in ${delay}ms`);
          await new Promise(resolve => setTimeout(resolve, delay));
        }
      }
    }

    // All retries exhausted
    console.error(`[API Failed] ${endpoint}: ${lastError?.message}`);
    return {
      status: 'error',
      error: 'network_error',
      message: lastError?.message ?? 'Request failed after retries',
      timestamp: new Date().toISOString()
    };
  }

  /**
   * GET request
   */
  async get<T>(endpoint: string, options?: RequestOptions): Promise<SuccessResponse<T> | ErrorResponse> {
    return this.request<T>(endpoint, { ...options, method: 'GET' });
  }

  /**
   * POST request
   */
  async post<T>(
    endpoint: string,
    body?: Record<string, any>,
    options?: RequestOptions
  ): Promise<SuccessResponse<T> | ErrorResponse> {
    return this.request<T>(endpoint, { ...options, method: 'POST', body });
  }

  /**
   * PUT request
   */
  async put<T>(
    endpoint: string,
    body?: Record<string, any>,
    options?: RequestOptions
  ): Promise<SuccessResponse<T> | ErrorResponse> {
    return this.request<T>(endpoint, { ...options, method: 'PUT', body });
  }

  /**
   * DELETE request
   */
  async delete<T>(endpoint: string, options?: RequestOptions): Promise<SuccessResponse<T> | ErrorResponse> {
    return this.request<T>(endpoint, { ...options, method: 'DELETE' });
  }

  /**
   * Get paginated results
   */
  async getPaginated<T>(
    endpoint: string,
    limit: number = 50,
    offset: number = 0,
    options?: RequestOptions
  ): Promise<PaginatedResponse<T> | ErrorResponse> {
    const url = `${endpoint}?limit=${limit}&offset=${offset}`;
    return this.request<T[]>(url, { ...options, method: 'GET' });
  }

  /**
   * Clear response cache
   */
  clearCache(): void {
    this.responseCache.clear();
    console.debug('[API] Response cache cleared');
  }

  /**
   * Get cache statistics
   */
  getCacheStats(): { size: number; entries: number; maxSize: number } {
    return {
      size: this.responseCache.size,
      entries: this.responseCache.size,
      maxSize: this.maxCacheSize,
    };
  }
}

// ============================================================================
// Specialized API Clients
// ============================================================================

/**
 * Cache-aware API client for chunk operations
 */
export class CacheAwareAPIClient {
  constructor(private apiClient: StandardizedAPIClient) {}

  /**
   * Get chunk with cache information
   */
  async getChunk(trackId: number, chunkIndex: number, preset?: string) {
    const endpoint = `/api/chunks/${trackId}/${chunkIndex}`;
    const response = await this.apiClient.get(endpoint, { cache: true });

    if (isSuccessResponse(response)) {
      return {
        data: response.data,
        cacheSource: response.cache_source ?? 'miss',
        cacheHit: response.cache_source !== undefined && response.cache_source !== 'miss',
        processingTimeMs: response.processing_time_ms ?? 0
      };
    }

    return { error: response };
  }

  /**
   * Get cache statistics
   */
  async getCacheStats(): Promise<CacheStats | null> {
    const response = await this.apiClient.get<CacheStats>('/api/cache/stats');

    if (isSuccessResponse<CacheStats>(response)) {
      return response.data;
    }

    return null;
  }

  /**
   * Get cache health status
   */
  async getCacheHealth(): Promise<CacheHealth | null> {
    const response = await this.apiClient.get<CacheHealth>('/api/cache/health');

    if (isSuccessResponse<CacheHealth>(response)) {
      return response.data;
    }

    return null;
  }
}

/**
 * Batch operations API client
 */
export class BatchAPIClient {
  constructor(private apiClient: StandardizedAPIClient) {}

  /**
   * Execute batch operation
   */
  async executeBatch(items: BatchItem[], atomic: boolean = false): Promise<BatchItemResult[] | null> {
    const request: BatchRequest = { items, atomic };
    const response = await this.apiClient.post<BatchItemResult[]>('/api/batch', request);

    if (isSuccessResponse<BatchItemResult[]>(response)) {
      return response.data;
    }

    console.error('Batch operation failed:', response);
    return null;
  }

  /**
   * Batch favorite tracks
   */
  async favoriteTracks(trackIds: string[]): Promise<boolean> {
    const items: BatchItem[] = trackIds.map(id => ({
      id,
      action: 'favorite'
    }));

    const results = await this.executeBatch(items, false);
    return results ? results.every(r => r.status === 'success') : false;
  }

  /**
   * Batch remove tracks
   */
  async removeTracks(trackIds: string[]): Promise<boolean> {
    const items: BatchItem[] = trackIds.map(id => ({
      id,
      action: 'remove'
    }));

    const results = await this.executeBatch(items, false);
    return results ? results.every(r => r.status === 'success') : false;
  }
}

/**
 * Create singleton API client instance
 */
let apiClientInstance: StandardizedAPIClient | null = null;

export function initializeAPIClient(config: APIClientConfig): StandardizedAPIClient {
  apiClientInstance = new StandardizedAPIClient(config);
  console.log('[API Client] Initialized with config:', {
    baseURL: config.baseURL,
    timeout: config.timeout ?? 30000,
    retryAttempts: config.retryAttempts ?? 3
  });
  return apiClientInstance;
}

export function getAPIClient(): StandardizedAPIClient {
  if (!apiClientInstance) {
    const baseURL = import.meta.env.VITE_API_URL ?? 'http://localhost:8765';
    apiClientInstance = initializeAPIClient({ baseURL });
  }
  return apiClientInstance;
}
