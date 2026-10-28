/**
 * useAlbumsQuery Hook Tests
 *
 * Tests for the convenience wrapper around useLibraryQuery('albums'). The
 * hook's one definition lives in useLibraryQueries.ts.
 *
 * @module hooks/library/__tests__/useLibraryQueries.albums.test
 */

import { renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useAlbumsQuery } from '../useLibraryQueries';
import { useLibraryQuery } from '../useLibraryQuery';
import type { UseLibraryQueryResult } from '../libraryQueryTypes';
import type { Track, Album, Artist } from '@/types/domain';

// Mock the underlying useLibraryQuery hook
vi.mock('../useLibraryQuery', () => ({
  useLibraryQuery: vi.fn(),
}));

// Typed as the hook's real result so the mocked useLibraryQuery accepts
// every per-test override (#5640).
const mockResult: UseLibraryQueryResult<Track | Album | Artist> = {
  data: [],
  total: 0,
  isLoading: false,
  isLoadingMore: false,
  error: null,
  loadMoreError: null,
  offset: 0,
  hasMore: false,
  fetchMore: vi.fn(),
  refetch: vi.fn(),
  clearError: vi.fn(),
};

describe('useAlbumsQuery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useLibraryQuery).mockReturnValue(mockResult);
  });

  it('should delegate to useLibraryQuery with type "albums"', () => {
    renderHook(() => useAlbumsQuery());

    expect(useLibraryQuery).toHaveBeenCalledWith('albums', undefined);
  });

  it('should pass options through to useLibraryQuery', () => {
    const options = { limit: 20, search: 'dark side', offset: 10 };

    renderHook(() => useAlbumsQuery(options));

    expect(useLibraryQuery).toHaveBeenCalledWith('albums', options);
  });

  it('should return the result from useLibraryQuery', () => {
    const albums = [
      { id: 1, title: 'Album A', artist: 'Artist', year: 2020, trackCount: 8 },
      { id: 2, title: 'Album B', artist: 'Artist', year: 2021, trackCount: 12 },
    ];
    const customResult = { ...mockResult, data: albums, total: 2 };
    vi.mocked(useLibraryQuery).mockReturnValue(customResult);

    const { result } = renderHook(() => useAlbumsQuery());

    expect(result.current.data).toEqual(albums);
    expect(result.current.total).toBe(2);
  });

  it('should propagate loading state', () => {
    vi.mocked(useLibraryQuery).mockReturnValue({ ...mockResult, isLoading: true });

    const { result } = renderHook(() => useAlbumsQuery());

    expect(result.current.isLoading).toBe(true);
  });

  it('should propagate error state', () => {
    const error = { message: 'Server error', code: 'QUERY_ERROR', status: 500 };
    vi.mocked(useLibraryQuery).mockReturnValue({ ...mockResult, error });

    const { result } = renderHook(() => useAlbumsQuery());

    expect(result.current.error).toEqual(error);
  });

  it('should propagate hasMore for pagination', () => {
    vi.mocked(useLibraryQuery).mockReturnValue({
      ...mockResult,
      hasMore: true,
      total: 100,
      data: Array(50).fill({ id: 1, title: 'A', artist: 'B', year: 2020, trackCount: 1 }),
    });

    const { result } = renderHook(() => useAlbumsQuery({ limit: 50 }));

    expect(result.current.hasMore).toBe(true);
    expect(result.current.total).toBe(100);
  });

  it('should expose fetchMore and refetch from underlying query', () => {
    const fetchMore = vi.fn();
    const refetch = vi.fn();
    vi.mocked(useLibraryQuery).mockReturnValue({ ...mockResult, fetchMore, refetch });

    const { result } = renderHook(() => useAlbumsQuery());

    expect(result.current.fetchMore).toBe(fetchMore);
    expect(result.current.refetch).toBe(refetch);
  });

  it('should work with search option', () => {
    renderHook(() => useAlbumsQuery({ search: 'abbey road' }));

    expect(useLibraryQuery).toHaveBeenCalledWith('albums', { search: 'abbey road' });
  });

  it('should work with no options', () => {
    renderHook(() => useAlbumsQuery());

    expect(useLibraryQuery).toHaveBeenCalledWith('albums', undefined);
  });

  it('should pass orderBy option through', () => {
    renderHook(() => useAlbumsQuery({ orderBy: 'year' }));

    expect(useLibraryQuery).toHaveBeenCalledWith('albums', { orderBy: 'year' });
  });
});
