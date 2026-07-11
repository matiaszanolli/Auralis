/**
 * Standardized API Hooks Tests
 *
 * Tests for the standardized API hooks including:
 * - usePaginatedAPI (pagination navigation)
 * - useCacheStats / useCacheHealth (cache monitoring)
 *
 * The generic useStandardizedAPI() fetch-on-mount hook was removed (#4300,
 * duplicate of useRestAPI) — see useRestAPI.test.ts for GET/POST/PUT/DELETE
 * coverage of the canonical generic hook.
 *
 * @module hooks/shared/__tests__/useStandardizedAPI.test
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
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

import { usePaginatedAPI } from '../useStandardizedAPI';

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

  it('passes an AbortSignal to nextPage and aborts it on unmount (#4174)', async () => {
    let nextPageSignal: AbortSignal | undefined;
    mockGetPaginated
      .mockResolvedValueOnce({
        success: true,
        data: [{ id: 1 }],
        pagination: { limit: 50, offset: 0, total: 100, has_more: true },
      })
      .mockImplementationOnce((_e: string, _l: number, _o: number, opts: any) => {
        nextPageSignal = opts?.signal;
        return new Promise(() => {}); // stays in flight
      });

    const { result, unmount } = renderHook(() => usePaginatedAPI('/api/items'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    act(() => {
      void result.current.pagination.nextPage();
    });

    // Previously nextPage passed no signal — now it does, and it is live.
    expect(nextPageSignal).toBeInstanceOf(AbortSignal);
    expect(nextPageSignal!.aborted).toBe(false);

    unmount();
    expect(nextPageSignal!.aborted).toBe(true);
  });

  it('passes an AbortSignal to goToPage and prevPage too (#4174)', async () => {
    const signals: (AbortSignal | undefined)[] = [];
    mockGetPaginated.mockImplementation((_e: string, _l: number, _o: number, opts: any) => {
      signals.push(opts?.signal);
      return Promise.resolve({
        success: true,
        data: [{ id: 1 }],
        pagination: { limit: 50, offset: 50, total: 100, has_more: true },
      });
    });

    const { result } = renderHook(() => usePaginatedAPI('/api/items'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.pagination.goToPage(3);
    });
    await act(async () => {
      await result.current.pagination.prevPage();
    });

    // Every manual page request (after the initial fetch) carries a signal.
    const manualSignals = signals.slice(1);
    expect(manualSignals.length).toBeGreaterThanOrEqual(2);
    expect(manualSignals.every((s) => s instanceof AbortSignal)).toBe(true);
  });
});

// Cache hooks (useCacheStats, useCacheHealth) depend on the internal
// getCacheClient() factory which requires integration-level setup.
// Covered by the cache integration tests instead.
