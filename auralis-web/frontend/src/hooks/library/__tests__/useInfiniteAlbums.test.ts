/**
 * useInfiniteAlbums Hook Tests
 *
 * Tests for TanStack Query-based infinite album scrolling.
 *
 * @module hooks/library/__tests__/useInfiniteAlbums.test
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// Mock dependencies before importing the hook
vi.mock('@/api/transformers', () => ({
  transformAlbumsResponse: vi.fn((data: any) => data),
}));

vi.mock('@/config/api', () => ({
  API_BASE_URL: 'http://localhost:8765',
}));

import { useInfiniteAlbums } from '../useInfiniteAlbums';
import { transformAlbumsResponse } from '@/api/transformers';

// Helper: create a fresh QueryClient wrapper for each test
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
}

// Helper: build a mock albums API response
function mockAlbumsPage(offset: number, limit: number, total: number) {
  const count = Math.min(limit, total - offset);
  const albums = Array.from({ length: count }, (_, i) => ({
    id: offset + i + 1,
    title: `Album ${offset + i + 1}`,
    artist: 'Test Artist',
    trackCount: 10,
    totalDuration: 3600,
    artworkUrl: null,
  }));
  return {
    albums,
    total,
    offset,
    limit,
    hasMore: offset + count < total,
  };
}

describe('useInfiniteAlbums', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.restoreAllMocks();
  });

  it('should fetch initial page of albums', async () => {
    const page = mockAlbumsPage(0, 50, 100);
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(page),
    } as Response);
    vi.mocked(transformAlbumsResponse).mockReturnValueOnce(page as any);

    const { result } = renderHook(() => useInfiniteAlbums(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.pages).toHaveLength(1);
    expect(result.current.data?.pages[0].albums).toHaveLength(50);
    expect(transformAlbumsResponse).toHaveBeenCalledWith(page);
  });

  it('should respect custom limit option', async () => {
    const page = mockAlbumsPage(0, 20, 30);
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(page),
    } as Response);
    vi.mocked(transformAlbumsResponse).mockReturnValueOnce(page as any);

    const { result } = renderHook(() => useInfiniteAlbums({ limit: 20 }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const fetchUrl = vi.mocked(globalThis.fetch).mock.calls[0][0] as string;
    expect(fetchUrl).toContain('limit=20');
  });

  it('should include search parameter in fetch URL', async () => {
    const page = mockAlbumsPage(0, 50, 1);
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(page),
    } as Response);
    vi.mocked(transformAlbumsResponse).mockReturnValueOnce(page as any);

    const { result } = renderHook(() => useInfiniteAlbums({ search: 'abbey' }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const fetchUrl = vi.mocked(globalThis.fetch).mock.calls[0][0] as string;
    expect(fetchUrl).toContain('search=abbey');
  });

  it('should report hasNextPage when more data available', async () => {
    const page = mockAlbumsPage(0, 50, 100);
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(page),
    } as Response);
    vi.mocked(transformAlbumsResponse).mockReturnValueOnce(page as any);

    const { result } = renderHook(() => useInfiniteAlbums(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.hasNextPage).toBe(true);
  });

  it('should report no next page when all data loaded', async () => {
    const page = mockAlbumsPage(0, 50, 10);
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(page),
    } as Response);
    vi.mocked(transformAlbumsResponse).mockReturnValueOnce(page as any);

    const { result } = renderHook(() => useInfiniteAlbums(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.hasNextPage).toBe(false);
  });

  it('should handle fetch error', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      statusText: 'Internal Server Error',
    } as Response);

    const { result } = renderHook(() => useInfiniteAlbums(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error?.message).toContain('Failed to fetch albums');
  });

  it('should not fetch when enabled is false', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockAlbumsPage(0, 50, 0)),
    } as Response);

    const { result } = renderHook(() => useInfiniteAlbums({ enabled: false }), {
      wrapper: createWrapper(),
    });

    // Flush microtasks to ensure any async effects have settled
    await act(async () => {});

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(result.current.data).toBeUndefined();
  });

  it('should handle network failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(new Error('Network error'));

    const { result } = renderHook(() => useInfiniteAlbums(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error?.message).toBe('Network error');
  });

  it('should start in loading state', () => {
    vi.spyOn(globalThis, 'fetch').mockReturnValue(new Promise(() => {})); // never resolves

    const { result } = renderHook(() => useInfiniteAlbums(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();
  });

  it('should transform API response through transformAlbumsResponse', async () => {
    const rawPage = mockAlbumsPage(0, 50, 5);
    const transformedPage = { ...rawPage, albums: rawPage.albums.map((a) => ({ ...a, transformed: true })) };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(rawPage),
    } as Response);
    vi.mocked(transformAlbumsResponse).mockReturnValueOnce(transformedPage as any);

    const { result } = renderHook(() => useInfiniteAlbums(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.pages[0]).toEqual(transformedPage);
  });

  it('should use correct query key based on search and limit', async () => {
    const page = mockAlbumsPage(0, 25, 5);
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(page),
    } as Response);
    vi.mocked(transformAlbumsResponse).mockReturnValueOnce(page as any);

    // Render with specific options - the query key should include them
    const { result } = renderHook(() => useInfiniteAlbums({ limit: 25, search: 'test' }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const fetchUrl = vi.mocked(globalThis.fetch).mock.calls[0][0] as string;
    expect(fetchUrl).toContain('limit=25');
    expect(fetchUrl).toContain('search=test');
    expect(fetchUrl).toContain('offset=0');
  });
});
