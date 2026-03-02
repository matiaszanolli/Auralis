/**
 * Tests for Standardized API Client
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Comprehensive tests for Phase C.1 frontend API integration.
 *
 * Test Coverage:
 * - API request/response handling
 * - Response validation and type guards
 * - Caching behavior and TTL
 * - Retry logic with exponential backoff
 * - Error handling
 * - Batch operations
 * - Cache statistics and health
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import {
  StandardizedAPIClient,
  CacheAwareAPIClient,
  BatchAPIClient,
  isSuccessResponse,
  isErrorResponse,
  isPaginatedResponse,
  APIClientConfig
} from '../standardizedAPIClient';

// ============================================================================
// Test Data
// ============================================================================

const mockConfig: APIClientConfig = {
  baseURL: 'http://localhost:8765',
  timeout: 5000,
  retryAttempts: 2,
  retryDelay: 100,
  cacheResponses: true,
  cacheTTL: 5000
};

const mockSuccessResponse = {
  status: 'success',
  data: { id: 1, name: 'Test' },
  timestamp: new Date().toISOString(),
  cache_source: 'miss',
  processing_time_ms: 2.5
};

const mockErrorResponse = {
  status: 'error',
  error: 'validation_error',
  message: 'Invalid request',
  timestamp: new Date().toISOString()
};

const mockPaginatedResponse = {
  status: 'success',
  data: [{ id: 1 }, { id: 2 }],
  pagination: {
    limit: 50,
    offset: 0,
    total: 100,
    remaining: 98,
    has_more: true
  },
  timestamp: new Date().toISOString()
};

// ============================================================================
// Type Guard Tests
// ============================================================================

describe('Type Guards', () => {
  it('should correctly identify success responses', () => {
    expect(isSuccessResponse(mockSuccessResponse)).toBe(true);
    expect(isSuccessResponse(mockErrorResponse)).toBe(false);
    expect(isSuccessResponse(null)).toBe(false);
  });

  it('should correctly identify error responses', () => {
    expect(isErrorResponse(mockErrorResponse)).toBe(true);
    expect(isErrorResponse(mockSuccessResponse)).toBe(false);
    expect(isErrorResponse(null)).toBe(false);
  });

  it('should correctly identify paginated responses', () => {
    expect(isPaginatedResponse(mockPaginatedResponse)).toBe(true);
    expect(isPaginatedResponse(mockSuccessResponse)).toBe(false);
    expect(isPaginatedResponse(mockErrorResponse)).toBe(false);
  });
});

// ============================================================================
// API Client Tests
// ============================================================================

describe('StandardizedAPIClient', () => {
  let client: StandardizedAPIClient;

  beforeEach(() => {
    client = new StandardizedAPIClient(mockConfig);
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should initialize with correct configuration', () => {
    expect(client).toBeDefined();
    expect(client.getCacheStats().size).toBe(0);
  });

  it('should make successful GET requests', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(mockSuccessResponse)
    });
    global.fetch = mockFetch;

    const result = await client.get('/api/test');

    expect(result.status).toBe('success');
    expect(isSuccessResponse(result)).toBe(true);
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/test'),
      expect.any(Object)
    );
  });

  it('should handle error responses', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      json: vi.fn().mockResolvedValue(mockErrorResponse)
    });
    global.fetch = mockFetch;

    const result = await client.get('/api/test');

    expect(result.status).toBe('error');
    expect(isErrorResponse(result)).toBe(true);
  });

  it('should cache GET responses', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(mockSuccessResponse)
    });
    global.fetch = mockFetch;

    // First request
    const result1 = await client.get('/api/test');
    expect(mockFetch).toHaveBeenCalledTimes(1);

    // Second request (should be cached)
    const result2 = await client.get('/api/test');
    expect(mockFetch).toHaveBeenCalledTimes(1); // Still 1, not 2

    expect(result1).toEqual(result2);
  });

  it('should respect cache TTL', async () => {
    const shortTTLClient = new StandardizedAPIClient({
      ...mockConfig,
      cacheTTL: 100
    });

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(mockSuccessResponse)
    });
    global.fetch = mockFetch;

    // First request
    await shortTTLClient.get('/api/test');
    expect(mockFetch).toHaveBeenCalledTimes(1);

    // Wait for cache to expire
    await new Promise(resolve => setTimeout(resolve, 150));

    // Second request (cache expired)
    await shortTTLClient.get('/api/test');
    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  it('should retry on network failures', async () => {
    const mockFetch = vi.fn()
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValue(mockSuccessResponse)
      });
    global.fetch = mockFetch;

    const result = await client.get('/api/test');

    expect(mockFetch).toHaveBeenCalledTimes(2); // Called twice due to retry
    expect(result.status).toBe('success');
  });

  it('should handle POST requests', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(mockSuccessResponse)
    });
    global.fetch = mockFetch;

    const body = { name: 'Test' };
    const result = await client.post('/api/test', body);

    expect(result.status).toBe('success');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(body)
      })
    );
  });

  it('should handle PUT requests', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(mockSuccessResponse)
    });
    global.fetch = mockFetch;

    const body = { name: 'Updated' };
    const result = await client.put('/api/test/1', body);

    expect(result.status).toBe('success');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        method: 'PUT'
      })
    );
  });

  it('should handle DELETE requests', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(mockSuccessResponse)
    });
    global.fetch = mockFetch;

    const result = await client.delete('/api/test/1');

    expect(result.status).toBe('success');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        method: 'DELETE'
      })
    );
  });

  it('should handle paginated responses', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(mockPaginatedResponse)
    });
    global.fetch = mockFetch;

    const result = await client.getPaginated('/api/test', 50, 0);

    expect(isPaginatedResponse(result)).toBe(true);
    expect((result as any).pagination.total).toBe(100);
    expect((result as any).pagination.has_more).toBe(true);
  });

  it('should clear cache', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(mockSuccessResponse)
    });
    global.fetch = mockFetch;

    // Add something to cache
    await client.get('/api/test');
    expect(client.getCacheStats().size).toBe(1);

    // Clear cache
    client.clearCache();
    expect(client.getCacheStats().size).toBe(0);
  });

  it('should keep cache size bounded at maxCacheSize entries after many unique calls', async () => {
    const MAX = 200;
    const boundedClient = new StandardizedAPIClient({ ...mockConfig, maxCacheSize: MAX });
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(mockSuccessResponse)
    });
    global.fetch = mockFetch;

    // Make 500 unique GET requests
    for (let i = 0; i < 500; i++) {
      await boundedClient.get(`/api/track/${i}`);
    }

    expect(boundedClient.getCacheStats().size).toBeLessThanOrEqual(MAX);
  });

  it('should evict the oldest entry when cache is full', async () => {
    const MAX = 3;
    const smallClient = new StandardizedAPIClient({ ...mockConfig, maxCacheSize: MAX });
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(mockSuccessResponse)
    });
    global.fetch = mockFetch;

    // Fill to capacity
    await smallClient.get('/api/a');
    await smallClient.get('/api/b');
    await smallClient.get('/api/c');
    expect(smallClient.getCacheStats().size).toBe(3);

    // One more entry — should evict /api/a (oldest)
    await smallClient.get('/api/d');
    expect(smallClient.getCacheStats().size).toBe(3);

    // /api/a is gone: next GET should hit the network, not the cache
    await smallClient.get('/api/a');
    // Without LRU eviction there would be 3 network calls (a, b, c, d) then a cache hit.
    // With LRU eviction /api/a was evicted, so the 5th call re-fetches it → 5 total.
    expect(mockFetch).toHaveBeenCalledTimes(5);
  });

  it('should delete stale entries eagerly on read', async () => {
    const expiredClient = new StandardizedAPIClient({ ...mockConfig, cacheTTL: 1 });
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(mockSuccessResponse)
    });
    global.fetch = mockFetch;

    await expiredClient.get('/api/stale');
    expect(expiredClient.getCacheStats().size).toBe(1);

    // Wait for TTL to expire
    await new Promise(resolve => setTimeout(resolve, 10));

    // Second GET — cache miss, stale entry removed
    await expiredClient.get('/api/stale');
    expect(mockFetch).toHaveBeenCalledTimes(2);
    // After the stale read-delete + re-set, still just 1 entry
    expect(expiredClient.getCacheStats().size).toBe(1);
  });
});

// ============================================================================
// Cache-Aware Client Tests
// ============================================================================

describe('CacheAwareAPIClient', () => {
  let client: StandardizedAPIClient;
  let cacheClient: CacheAwareAPIClient;

  beforeEach(() => {
    client = new StandardizedAPIClient(mockConfig);
    cacheClient = new CacheAwareAPIClient(client);
  });

  it('should get chunk with cache information', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({
        ...mockSuccessResponse,
        data: { chunk: 'data' },
        cache_source: 'tier1'
      })
    });
    global.fetch = mockFetch;

    const result = await cacheClient.getChunk(1, 0);

    expect(result.cacheSource).toBe('tier1');
    expect(result.cacheHit).toBe(true);
    expect(result.processingTimeMs).toBeDefined();
  });

  it('should get cache stats', async () => {
    const mockStats = {
      tier1: {
        chunks: 4,
        size_mb: 6.0,
        hits: 150,
        misses: 10,
        hit_rate: 0.938
      },
      tier2: {
        chunks: 146,
        size_mb: 219.0,
        hits: 1350,
        misses: 90,
        hit_rate: 0.937
      },
      overall: {
        total_chunks: 150,
        total_size_mb: 225.0,
        total_hits: 1500,
        total_misses: 100,
        overall_hit_rate: 0.938,
        tracks_cached: 5
      },
      tracks: {}
    };

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({
        ...mockSuccessResponse,
        data: mockStats
      })
    });
    global.fetch = mockFetch;

    const stats = await cacheClient.getCacheStats();

    expect(stats).not.toBeNull();
    expect(stats?.overall.overall_hit_rate).toBe(0.938);
  });

  it('should get cache health', async () => {
    const mockHealth = {
      healthy: true,
      tier1_size_mb: 6.0,
      tier1_healthy: true,
      tier2_size_mb: 200.0,
      tier2_healthy: true,
      total_size_mb: 206.0,
      memory_healthy: true,
      tier1_hit_rate: 0.95,
      overall_hit_rate: 0.938,
      timestamp: new Date().toISOString()
    };

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({
        ...mockSuccessResponse,
        data: mockHealth
      })
    });
    global.fetch = mockFetch;

    const health = await cacheClient.getCacheHealth();

    expect(health).not.toBeNull();
    expect(health?.healthy).toBe(true);
  });
});

// ============================================================================
// Batch Client Tests
// ============================================================================

describe('BatchAPIClient', () => {
  let client: StandardizedAPIClient;
  let batchClient: BatchAPIClient;

  beforeEach(() => {
    client = new StandardizedAPIClient(mockConfig);
    batchClient = new BatchAPIClient(client);
  });

  it('should execute batch operations', async () => {
    const mockResults = [
      { id: '1', status: 'success', message: 'Success' },
      { id: '2', status: 'success', message: 'Success' }
    ];

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({
        ...mockSuccessResponse,
        data: mockResults
      })
    });
    global.fetch = mockFetch;

    const items = [
      { id: '1', action: 'favorite' },
      { id: '2', action: 'favorite' }
    ];

    const results = await batchClient.executeBatch(items);

    expect(results).not.toBeNull();
    expect(results?.length).toBe(2);
    expect(results?.[0].status).toBe('success');
  });

  it('should favorite multiple tracks', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({
        status: 'success',
        data: [
          { id: '1', status: 'success' },
          { id: '2', status: 'success' }
        ]
      })
    });
    global.fetch = mockFetch;

    const success = await batchClient.favoriteTracks(['1', '2']);

    expect(success).toBe(true);
    expect(mockFetch).toHaveBeenCalled();
  });

  it('should remove multiple tracks', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({
        status: 'success',
        data: [
          { id: '1', status: 'success' },
          { id: '2', status: 'success' }
        ]
      })
    });
    global.fetch = mockFetch;

    const success = await batchClient.removeTracks(['1', '2']);

    expect(success).toBe(true);
  });
});
