/**
 * useInfiniteAlbums Hook Tests
 *
 * Tests for TanStack Query-based infinite album scrolling.
 *
 * #5519: the query function went through a bare fetch() with no timeout (a
 * stalled backend left the grid's loading states pending forever — #5019's
 * bug class); it now uses the shared `get()` transport, so these tests mock
 * `@/utils/apiRequest` instead of globalThis.fetch.
 *
 * @module hooks/library/__tests__/useInfiniteAlbums.test
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactNode, createElement } from 'react';
// Mock dependencies before importing the hook
vi.mock('@/api/transformers', () => ({
  transformAlbumsResponse: vi.fn((data: any) => data),
}));

const { getMock } = vi.hoisted(() => ({ getMock: vi.fn() }));
vi.mock('@/utils/apiRequest', () => ({
  get: getMock,
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
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
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
    getMock.mockResolvedValue({});
  });

  it('should fetch initial page of albums', async () => {
    const page = mockAlbumsPage(0, 50, 100);
    getMock.mockResolvedValueOnce(page);
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
    getMock.mockResolvedValueOnce(page);

    const { result } = renderHook(() => useInfiniteAlbums({ limit: 20 }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const endpoint = getMock.mock.calls[0][0] as string;
    expect(endpoint).toContain('limit=20');
  });

  it('should include search parameter in fetch URL', async () => {
    const page = mockAlbumsPage(0, 50, 1);
    getMock.mockResolvedValueOnce(page);

    const { result } = renderHook(() => useInfiniteAlbums({ search: 'abbey' }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const endpoint = getMock.mock.calls[0][0] as string;
    expect(endpoint).toContain('search=abbey');
  });

  it('should report hasNextPage when more data available', async () => {
    const page = mockAlbumsPage(0, 50, 100);
    getMock.mockResolvedValueOnce(page);

    const { result } = renderHook(() => useInfiniteAlbums(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.hasNextPage).toBe(true);
  });

  it('should report no next page when all data loaded', async () => {
    const page = mockAlbumsPage(0, 50, 10);
    getMock.mockResolvedValueOnce(page);

    const { result } = renderHook(() => useInfiniteAlbums(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.hasNextPage).toBe(false);
  });

  it('propagates the transport error with the backend detail (#4626)', async () => {
    // apiRequest parses the body's detail and throws with it; the hook must
    // surface that message, not wrap or discard it.
    getMock.mockRejectedValueOnce(new Error('Library database is locked'));

    const { result } = renderHook(() => useInfiniteAlbums(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error?.message).toBe('Library database is locked');
  });

  it('a rejected transport promise becomes a retryable error state', async () => {
    // The #5519 point: the shared transport rejects on timeout, which
    // TanStack Query can retry — a hung bare fetch() never rejected at all.
    getMock.mockRejectedValueOnce(new Error('Request timed out after 30000ms'));

    const { result } = renderHook(() => useInfiniteAlbums(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error?.message).toContain('timed out');
  });

  it('should not fetch when enabled is false', async () => {
    const { result } = renderHook(() => useInfiniteAlbums({ enabled: false }), {
      wrapper: createWrapper(),
    });

    // Flush microtasks to ensure any async effects have settled
    await act(async () => {});

    expect(getMock).not.toHaveBeenCalled();
    expect(result.current.data).toBeUndefined();
  });

  it('should handle network failure', async () => {
    getMock.mockRejectedValueOnce(new TypeError('Network error'));

    const { result } = renderHook(() => useInfiniteAlbums(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error?.message).toBe('Network error');
  });

  it('should start in loading state', () => {
    getMock.mockReturnValue(new Promise(() => {})); // never resolves

    const { result } = renderHook(() => useInfiniteAlbums(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();
  });

  it('should transform API response through transformAlbumsResponse', async () => {
    const rawPage = mockAlbumsPage(0, 50, 5);
    const transformedPage = { ...rawPage, albums: rawPage.albums.map((a) => ({ ...a, transformed: true })) };

    getMock.mockResolvedValueOnce(rawPage);
    vi.mocked(transformAlbumsResponse).mockReturnValueOnce(transformedPage as any);

    const { result } = renderHook(() => useInfiniteAlbums(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.pages[0]).toEqual(transformedPage);
  });

  it('should use correct query key based on search and limit', async () => {
    const page = mockAlbumsPage(0, 25, 5);
    getMock.mockResolvedValueOnce(page);

    // Render with specific options - the query key should include them
    const { result } = renderHook(() => useInfiniteAlbums({ limit: 25, search: 'test' }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const endpoint = getMock.mock.calls[0][0] as string;
    expect(endpoint).toContain('limit=25');
    expect(endpoint).toContain('search=test');
    expect(endpoint).toContain('offset=0');
  });

  it('sends the sort as a server order, A-Z by default (#5868)', async () => {
    getMock.mockResolvedValueOnce(mockAlbumsPage(0, 50, 5));

    const { result } = renderHook(() => useInfiniteAlbums(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const params = new URL(getMock.mock.calls[0][0] as string, 'http://x').searchParams;
    expect(params.get('order_by')).toBe('title');
    expect(params.get('order')).toBe('asc');
  });

  it('a different sort is a different query, fetched from offset 0 (#5868)', async () => {
    getMock.mockImplementation(async () => mockAlbumsPage(0, 50, 5));

    const { result, rerender } = renderHook(
      ({ order }: { order: 'asc' | 'desc' }) => useInfiniteAlbums({ orderBy: 'year', order }),
      { wrapper: createWrapper(), initialProps: { order: 'asc' as 'asc' | 'desc' } },
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    rerender({ order: 'desc' });
    await waitFor(() => expect(getMock).toHaveBeenCalledTimes(2));

    const second = new URL(getMock.mock.calls[1][0] as string, 'http://x').searchParams;
    expect(second.get('order_by')).toBe('year');
    expect(second.get('order')).toBe('desc');
    expect(second.get('offset')).toBe('0');
  });
});
