/**
 * useStandardizedAPI Hook Tests
 *
 * Tests for the standardized API hooks including:
 * - useStandardizedAPI (GET, POST, PUT, DELETE)
 * - usePaginatedAPI (pagination navigation)
 * - useCacheStats / useCacheHealth (cache monitoring)
 *
 * @module hooks/shared/__tests__/useStandardizedAPI.test
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
// Mock the API client module
const mockGet = vi.fn();
const mockPost = vi.fn();
const mockPut = vi.fn();
const mockDelete = vi.fn();
const mockGetPaginated = vi.fn();
const mockGetCacheStats = vi.fn();
const mockGetCacheHealth = vi.fn();
const mockExecuteBatch = vi.fn();
const mockFavoriteTracks = vi.fn();
const mockRemoveTracks = vi.fn();

vi.mock('@/services/api/standardizedAPIClient', () => ({
  getAPIClient: vi.fn(() => ({
    get: mockGet,
    post: mockPost,
    put: mockPut,
    delete: mockDelete,
    getPaginated: mockGetPaginated,
  })),
  initializeAPIClient: vi.fn(),
  isSuccessResponse: vi.fn((r: any) => r?.success === true),
  CacheAwareAPIClient: vi.fn().mockImplementation(() => ({
    getCacheStats: mockGetCacheStats,
    getCacheHealth: mockGetCacheHealth,
  })),
  BatchAPIClient: vi.fn().mockImplementation(() => ({
    executeBatch: mockExecuteBatch,
    favoriteTracks: mockFavoriteTracks,
    removeTracks: mockRemoveTracks,
  })),
  StandardizedAPIClient: vi.fn(),
}));

vi.mock('@/config/api', () => ({
  API_BASE_URL: 'http://localhost:8765',
}));

import {
  useStandardizedAPI,
  usePaginatedAPI,
} from '../useStandardizedAPI';

describe('useStandardizedAPI', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should start with loading state', () => {
    mockGet.mockReturnValue(new Promise(() => {})); // never resolves

    const { result } = renderHook(() => useStandardizedAPI('/api/test'));

    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('should fetch data on mount with GET by default', async () => {
    mockGet.mockResolvedValueOnce({
      success: true,
      data: { tracks: [1, 2, 3] },
      cache_source: 'miss',
      processing_time_ms: 42,
    });

    const { result } = renderHook(() =>
      useStandardizedAPI<{ tracks: number[] }>('/api/tracks')
    );

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.data).toEqual({ tracks: [1, 2, 3] });
    expect(result.current.error).toBeNull();
    expect(result.current.cacheSource).toBe('miss');
    expect(result.current.processingTimeMs).toBe(42);
  });

  it('should handle error response', async () => {
    mockGet.mockResolvedValueOnce({
      success: false,
      message: 'Not found',
    });

    const { result } = renderHook(() => useStandardizedAPI('/api/missing'));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.data).toBeNull();
    expect(result.current.error).toBe('Not found');
  });

  it('should handle thrown error', async () => {
    mockGet.mockRejectedValueOnce(new Error('Network timeout'));

    const { result } = renderHook(() => useStandardizedAPI('/api/test'));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe('Network timeout');
  });

  it('should use POST method when specified', async () => {
    mockPost.mockResolvedValueOnce({
      success: true,
      data: { id: 1 },
    });

    const { result } = renderHook(() =>
      useStandardizedAPI('/api/items', {
        method: 'POST',
        body: { name: 'test' },
      })
    );

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(mockPost).toHaveBeenCalledWith(
      '/api/items',
      { name: 'test' },
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('should not auto-fetch when autoFetch is false', async () => {
    const { result } = renderHook(() =>
      useStandardizedAPI('/api/test', { autoFetch: false })
    );

    // Give it time to potentially fire
    await new Promise((r) => setTimeout(r, 50));

    expect(mockGet).not.toHaveBeenCalled();
    expect(result.current.loading).toBe(true);
  });

  it('should support manual refetch', async () => {
    mockGet
      .mockResolvedValueOnce({ success: true, data: 'first' })
      .mockResolvedValueOnce({ success: true, data: 'second' });

    const { result } = renderHook(() => useStandardizedAPI<string>('/api/test'));

    await waitFor(() => expect(result.current.data).toBe('first'));

    await act(async () => {
      await result.current.refetch();
    });

    expect(result.current.data).toBe('second');
  });

  it('should reset state via reset()', async () => {
    mockGet.mockResolvedValueOnce({ success: true, data: 'value' });

    const { result } = renderHook(() => useStandardizedAPI<string>('/api/test'));

    await waitFor(() => expect(result.current.data).toBe('value'));

    act(() => {
      result.current.reset();
    });

    expect(result.current.data).toBeNull();
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('should handle non-Error thrown values', async () => {
    mockGet.mockRejectedValueOnce('raw string error');

    const { result } = renderHook(() => useStandardizedAPI('/api/test'));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe('Unknown error occurred');
  });
});

describe('usePaginatedAPI', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should fetch first page on mount', async () => {
    mockGetPaginated.mockResolvedValueOnce({
      success: true,
      data: [{ id: 1 }, { id: 2 }],
      pagination: { limit: 50, offset: 0, total: 100, has_more: true },
    });

    const { result } = renderHook(() => usePaginatedAPI('/api/items'));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.data).toEqual([{ id: 1 }, { id: 2 }]);
    expect(result.current.pagination.total).toBe(100);
    expect(result.current.pagination.hasMore).toBe(true);
    expect(result.current.pagination.offset).toBe(0);
  });

  it('should navigate to next page', async () => {
    mockGetPaginated
      .mockResolvedValueOnce({
        success: true,
        data: [{ id: 1 }],
        pagination: { limit: 50, offset: 0, total: 100, has_more: true },
      })
      .mockResolvedValueOnce({
        success: true,
        data: [{ id: 51 }],
        pagination: { limit: 50, offset: 50, total: 100, has_more: false },
      });

    const { result } = renderHook(() => usePaginatedAPI('/api/items'));

    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.pagination.nextPage();
    });

    expect(result.current.pagination.offset).toBe(50);
    expect(result.current.pagination.hasMore).toBe(false);
  });

  it('should not go to next page when no more data', async () => {
    mockGetPaginated.mockResolvedValueOnce({
      success: true,
      data: [{ id: 1 }],
      pagination: { limit: 50, offset: 0, total: 1, has_more: false },
    });

    const { result } = renderHook(() => usePaginatedAPI('/api/items'));

    await waitFor(() => expect(result.current.loading).toBe(false));

    const callCount = mockGetPaginated.mock.calls.length;

    await act(async () => {
      await result.current.pagination.nextPage();
    });

    // Should not have made another request
    expect(mockGetPaginated.mock.calls.length).toBe(callCount);
  });

  it('should go to specific page', async () => {
    mockGetPaginated
      .mockResolvedValueOnce({
        success: true,
        data: [{ id: 1 }],
        pagination: { limit: 10, offset: 0, total: 50, has_more: true },
      })
      .mockResolvedValueOnce({
        success: true,
        data: [{ id: 31 }],
        pagination: { limit: 10, offset: 30, total: 50, has_more: true },
      });

    const { result } = renderHook(() =>
      usePaginatedAPI('/api/items', { initialLimit: 10 })
    );

    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.pagination.goToPage(4); // page 4 = offset 30
    });

    expect(result.current.pagination.offset).toBe(30);
  });

  it('should handle pagination error', async () => {
    mockGetPaginated.mockRejectedValueOnce(new Error('Server error'));

    const { result } = renderHook(() => usePaginatedAPI('/api/items'));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe('Server error');
    expect(result.current.data).toEqual([]);
  });

  it('should reset pagination state', async () => {
    mockGetPaginated.mockResolvedValueOnce({
      success: true,
      data: [{ id: 1 }],
      pagination: { limit: 50, offset: 0, total: 100, has_more: true },
    });

    const { result } = renderHook(() => usePaginatedAPI('/api/items'));

    await waitFor(() => expect(result.current.loading).toBe(false));

    act(() => {
      result.current.reset();
    });

    expect(result.current.data).toEqual([]);
    expect(result.current.pagination.offset).toBe(0);
    expect(result.current.pagination.total).toBe(0);
    expect(result.current.pagination.hasMore).toBe(false);
  });
});

// Cache hooks (useCacheStats, useCacheHealth) depend on the internal
// getCacheClient() factory which requires integration-level setup.
// Covered by the cache integration tests instead.
