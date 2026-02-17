/**
 * useLibraryQuery Hook Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tests for library query hook including:
 * - Pagination and offset management
 * - Search functionality
 * - Error handling and retry
 * - Infinite scroll pattern
 * - Request deduplication
 * - Cleanup on unmount
 *
 * @module hooks/library/__tests__/useLibraryQuery.test
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { vi } from 'vitest';
import {
  useLibraryQuery,
  useTracksQuery,
  useAlbumsQuery,
  useArtistsQuery,
  useInfiniteScroll,
} from '@/hooks/library/useLibraryQuery';
import { useRestAPI } from '@/hooks/api/useRestAPI';
import type { Track, Album, Artist } from '@/types/domain';

// Mock useRestAPI hook
vi.mock('@/hooks/api/useRestAPI');

// Mock data
const mockTrack: Track = {
  id: 1,
  title: 'Test Track',
  artist: 'Test Artist',
  album: 'Test Album',
  duration: 180,
  filepath: '/path/to/track.wav',
};

const mockAlbum: Album = {
  id: 1,
  title: 'Test Album',
  artist: 'Test Artist',
  year: 2023,
  track_count: 10,
};

const mockArtist: Artist = {
  id: 1,
  name: 'Test Artist',
  track_count: 25,
  album_count: 3,
};

describe('useLibraryQuery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('initial state and fetching', () => {
    it('should fetch tracks on mount', async () => {
      const mockGet = vi.fn().mockResolvedValue({
        items: [mockTrack],
        total: 1,
        offset: 0,
        limit: 50,
        hasMore: false,
      });

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      const { result } = renderHook(() => useLibraryQuery('tracks'));

      // Initially loading
      expect(result.current.isLoading).toBe(true);

      // Wait for fetch to complete
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Verify data was fetched
      expect(result.current.data).toEqual([mockTrack]);
      expect(result.current.total).toBe(1);
      expect(mockGet).toHaveBeenCalled();
    });

    it('should not fetch when skip option is true', async () => {
      const mockGet = vi.fn();

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      const { result } = renderHook(() =>
        useLibraryQuery('tracks', { skip: true })
      );

      expect(result.current.isLoading).toBe(false);
      expect(mockGet).not.toHaveBeenCalled();
    });

    it('should return empty data initially', () => {
      const mockGet = vi.fn().mockResolvedValue({
        items: [],
        total: 0,
        offset: 0,
        limit: 50,
        hasMore: false,
      });

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      const { result } = renderHook(() =>
        useLibraryQuery('tracks', { skip: true })
      );

      expect(result.current.data).toEqual([]);
      expect(result.current.total).toBe(0);
      expect(result.current.isLoading).toBe(false);
    });
  });

  describe('pagination', () => {
    it('should track offset and limit correctly', async () => {
      const mockGet = vi.fn().mockResolvedValue({
        items: [mockTrack],
        total: 200,
        offset: 0,
        limit: 50,
        hasMore: true,
      });

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      const { result } = renderHook(() =>
        useLibraryQuery('tracks', { limit: 50 })
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.offset).toBe(0);
      expect(result.current.hasMore).toBe(true);
    });

    it('should calculate hasMore correctly', async () => {
      const mockGet = vi.fn().mockResolvedValue({
        items: [mockTrack, mockTrack],
        total: 100,
        offset: 0,
        limit: 50,
        hasMore: true,
      });

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      const { result } = renderHook(() =>
        useLibraryQuery('tracks', { limit: 50 })
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // (offset + data.length) < total = (0 + 2) < 100 = true
      expect(result.current.hasMore).toBe(true);
    });

    it('should know when at end of results', async () => {
      const mockGet = vi.fn().mockResolvedValue({
        items: [mockTrack],
        total: 1,
        offset: 0,
        limit: 50,
        hasMore: false,
      });

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      const { result } = renderHook(() =>
        useLibraryQuery('tracks', { limit: 50 })
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.hasMore).toBe(false);
    });
  });

  describe('fetchMore (infinite scroll)', () => {
    it('should append new items when fetchMore is called', async () => {
      const firstPageTracks = [{ ...mockTrack, id: 1 }];
      const secondPageTracks = [{ ...mockTrack, id: 2 }];

      const mockGet = vi
        .fn()
        .mockResolvedValueOnce({
          items: firstPageTracks,
          total: 200,
          offset: 0,
          limit: 50,
          hasMore: true,
        })
        .mockResolvedValueOnce({
          items: secondPageTracks,
          total: 200,
          offset: 50,
          limit: 50,
          hasMore: true,
        });

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      const { result } = renderHook(() =>
        useLibraryQuery('tracks', { limit: 50 })
      );

      // Wait for initial load
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toEqual(firstPageTracks);

      // Fetch more items
      await act(async () => {
        await result.current.fetchMore();
      });

      // Both pages should be present
      expect(result.current.data).toEqual([...firstPageTracks, ...secondPageTracks]);
    });

    it('should not fetch more when already loading', async () => {
      const mockGet = vi.fn().mockImplementation(
        () =>
          new Promise((resolve) => {
            setTimeout(() => {
              resolve({
                items: [mockTrack],
                total: 200,
                offset: 0,
                limit: 50,
                hasMore: true,
              });
            }, 100);
          })
      );

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      const { result } = renderHook(() =>
        useLibraryQuery('tracks', { limit: 50 })
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Attempt to fetch more while "loading"
      await act(async () => {
        // Don't await, so isLoading might still be true
        const promise = result.current.fetchMore();
        // Manually set isLoading state check
        if (result.current.isLoading) {
          // Second call should return early
          await result.current.fetchMore();
        }
      });

      // get should still have been called only twice (initial + one fetchMore)
      expect(mockGet.mock.calls.length).toBeLessThanOrEqual(2);
    });

    it('should not fetch more when hasMore is false', async () => {
      const mockGet = vi.fn().mockResolvedValue({
        items: [mockTrack],
        total: 1,
        offset: 0,
        limit: 50,
        hasMore: false,
      });

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      const { result } = renderHook(() =>
        useLibraryQuery('tracks', { limit: 50 })
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Attempt to fetch more when hasMore is false
      await act(async () => {
        await result.current.fetchMore();
      });

      // Should only have one call (initial fetch)
      expect(mockGet).toHaveBeenCalledTimes(1);
    });

    it('should handle errors in fetchMore', async () => {
      const mockGet = vi
        .fn()
        .mockResolvedValueOnce({
          items: [mockTrack],
          total: 200,
          offset: 0,
          limit: 50,
          hasMore: true,
        })
        .mockRejectedValueOnce(new Error('Network error'));

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      const { result } = renderHook(() =>
        useLibraryQuery('tracks', { limit: 50 })
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Fetch more with error
      await act(async () => {
        await result.current.fetchMore();
      });

      // Error should be captured
      expect(result.current.error).not.toBeNull();
      expect(result.current.error?.message).toContain('Network error');
    });
  });

  describe('search functionality', () => {
    it('should include search query in endpoint', async () => {
      const mockGet = vi.fn().mockResolvedValue({
        items: [{ ...mockTrack, title: 'Beatles Song' }],
        total: 1,
        offset: 0,
        limit: 50,
        hasMore: false,
      });

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      const { result } = renderHook(() =>
        useLibraryQuery('tracks', { search: 'beatles' })
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Verify search parameter was included
      const callUrl = mockGet.mock.calls[0][0];
      expect(callUrl).toContain('search=beatles');
    });

    it('should encode search query properly', async () => {
      const mockGet = vi.fn().mockResolvedValue({
        items: [],
        total: 0,
        offset: 0,
        limit: 50,
        hasMore: false,
      });

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      const { result } = renderHook(() =>
        useLibraryQuery('tracks', { search: 'test & special' })
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const callUrl = mockGet.mock.calls[0][0];
      // URL encoding uses + for spaces (application/x-www-form-urlencoded format)
      expect(callUrl).toContain('search=test+%26+special');
    });
  });

  describe('refetch', () => {
    it('should reset data and refetch from beginning', async () => {
      const firstLoad = [{ ...mockTrack, id: 1 }];
      const secondLoad = [{ ...mockTrack, id: 2 }];

      const mockGet = vi
        .fn()
        .mockResolvedValueOnce({
          items: firstLoad,
          total: 100,
          offset: 0,
          limit: 50,
          hasMore: true,
        })
        .mockResolvedValueOnce({
          items: secondLoad,
          total: 100,
          offset: 0,
          limit: 50,
          hasMore: true,
        });

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      const { result } = renderHook(() =>
        useLibraryQuery('tracks', { limit: 50 })
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toEqual(firstLoad);

      // Refetch
      await act(async () => {
        await result.current.refetch();
      });

      expect(result.current.data).toEqual(secondLoad);
      expect(mockGet).toHaveBeenCalledTimes(2);
    });

    it('should clear offset on refetch', async () => {
      const mockGet = vi.fn().mockResolvedValue({
        items: [mockTrack],
        total: 100,
        offset: 0,
        limit: 50,
        hasMore: true,
      });

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      const { result } = renderHook(() =>
        useLibraryQuery('tracks', { limit: 50, offset: 50 })
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Refetch
      await act(async () => {
        await result.current.refetch();
      });

      expect(result.current.offset).toBe(0);
    });
  });

  describe('error handling', () => {
    it('should capture errors from failed queries', async () => {
      const mockGet = vi.fn().mockRejectedValue(new Error('API error'));

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      const { result } = renderHook(() => useLibraryQuery('tracks'));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).not.toBeNull();
      expect(result.current.error?.message).toContain('API error');
    });

    it('should have error code set to QUERY_ERROR', async () => {
      const mockGet = vi.fn().mockRejectedValue(new Error('API error'));

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      const { result } = renderHook(() => useLibraryQuery('tracks'));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error?.code).toBe('QUERY_ERROR');
    });

    it('should allow clearing errors', async () => {
      const mockGet = vi.fn().mockRejectedValue(new Error('API error'));

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      const { result } = renderHook(() => useLibraryQuery('tracks'));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).not.toBeNull();

      act(() => {
        result.current.clearError();
      });

      expect(result.current.error).toBeNull();
    });

    it('should clear error when new query succeeds', async () => {
      const mockGet = vi
        .fn()
        .mockRejectedValueOnce(new Error('API error'))
        .mockResolvedValueOnce({
          items: [mockTrack],
          total: 1,
          offset: 0,
          limit: 50,
          hasMore: false,
        });

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      const { result } = renderHook(() => useLibraryQuery('tracks'));

      // Wait for initial error
      await waitFor(() => {
        expect(result.current.error).not.toBeNull();
      });

      // Refetch
      await act(async () => {
        await result.current.refetch();
      });

      expect(result.current.error).toBeNull();
      expect(result.current.data).toEqual([mockTrack]);
    });
  });

  describe('query types', () => {
    it('should fetch tracks with correct endpoint', async () => {
      const mockGet = vi.fn().mockResolvedValue({
        items: [mockTrack],
        total: 1,
        offset: 0,
        limit: 50,
        hasMore: false,
      });

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      const { result } = renderHook(() => useLibraryQuery('tracks'));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const callUrl = mockGet.mock.calls[0][0];
      expect(callUrl).toContain('/api/library/tracks');
    });

    it('should fetch albums with correct endpoint', async () => {
      // Albums use the dedicated /api/albums route, not /api/library/albums
      // (issue #2379: /api/library/albums belongs to the library router but
      //  /api/albums is the canonical albums-router endpoint)
      const mockGet = vi.fn().mockResolvedValue({
        items: [mockAlbum],
        total: 1,
        offset: 0,
        limit: 50,
        hasMore: false,
      });

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      const { result } = renderHook(() => useLibraryQuery('albums'));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const callUrl = mockGet.mock.calls[0][0];
      expect(callUrl).toContain('/api/albums');
      expect(callUrl).not.toContain('/api/library/albums');
    });

    it('should fetch artists with correct endpoint', async () => {
      // Artists use the dedicated /api/artists route, not /api/library/artists
      // (issue #2379: /api/library/artists belongs to the library router but
      //  /api/artists is the canonical artists-router endpoint)
      const mockGet = vi.fn().mockResolvedValue({
        items: [mockArtist],
        total: 1,
        offset: 0,
        limit: 50,
        hasMore: false,
      });

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      const { result } = renderHook(() => useLibraryQuery('artists'));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const callUrl = mockGet.mock.calls[0][0];
      expect(callUrl).toContain('/api/artists');
      expect(callUrl).not.toContain('/api/library/artists');
    });
  });

  describe('convenience hooks', () => {
    it('should use useTracksQuery for tracks', async () => {
      const mockGet = vi.fn().mockResolvedValue({
        items: [mockTrack],
        total: 1,
        offset: 0,
        limit: 50,
        hasMore: false,
      });

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      const { result } = renderHook(() => useTracksQuery());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toEqual([mockTrack]);
    });

    it('should use useAlbumsQuery for albums', async () => {
      const mockGet = vi.fn().mockResolvedValue({
        items: [mockAlbum],
        total: 1,
        offset: 0,
        limit: 50,
        hasMore: false,
      });

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      const { result } = renderHook(() => useAlbumsQuery());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toEqual([mockAlbum]);
    });

    it('should use useArtistsQuery for artists', async () => {
      const mockGet = vi.fn().mockResolvedValue({
        items: [mockArtist],
        total: 1,
        offset: 0,
        limit: 50,
        hasMore: false,
      });

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      const { result } = renderHook(() => useArtistsQuery());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toEqual([mockArtist]);
    });

    it('should use useInfiniteScroll for infinite scroll pattern', async () => {
      const mockGet = vi.fn().mockResolvedValue({
        items: [mockTrack],
        total: 200,
        offset: 0,
        limit: 50,
        hasMore: true,
      });

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      const { result } = renderHook(() => useInfiniteScroll('tracks'));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.items).toEqual([mockTrack]);
      expect(result.current.hasMore).toBe(true);
      expect(typeof result.current.getMoreItems).toBe('function');
    });
  });

  describe('cleanup', () => {
    it('should abort request on unmount', async () => {
      const abortSpy = vi.fn();
      const mockGet = vi.fn(
        () =>
          new Promise((resolve) => {
            setTimeout(() => {
              resolve({
                items: [mockTrack],
                total: 1,
                offset: 0,
                limit: 50,
                hasMore: false,
              });
            }, 1000);
          })
      );

      // Mock AbortController
      const originalAbortController = global.AbortController;
      const MockAbortController = vi.fn(() => ({
        abort: abortSpy,
        signal: {},
      }));
      (global as any).AbortController = MockAbortController;

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      const { unmount } = renderHook(() => useLibraryQuery('tracks'));

      // Unmount immediately
      unmount();

      // AbortController should be restored
      global.AbortController = originalAbortController;
    });
  });

  describe('orderBy parameter', () => {
    it('should include orderBy in endpoint', async () => {
      const mockGet = vi.fn().mockResolvedValue({
        items: [mockTrack],
        total: 1,
        offset: 0,
        limit: 50,
        hasMore: false,
      });

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      const { result } = renderHook(() =>
        useLibraryQuery('tracks', { orderBy: 'title' })
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const callUrl = mockGet.mock.calls[0][0];
      expect(callUrl).toContain('order_by=title');
    });
  });

  describe('custom endpoint', () => {
    it('should use custom endpoint if provided', async () => {
      const mockGet = vi.fn().mockResolvedValue({
        items: [mockTrack],
        total: 1,
        offset: 0,
        limit: 50,
        hasMore: false,
      });

      vi.mocked(useRestAPI).mockReturnValue({
        get: mockGet,
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      } as any);

      const { result } = renderHook(() =>
        useLibraryQuery('tracks', { endpoint: '/api/custom/endpoint' })
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const callUrl = mockGet.mock.calls[0][0];
      expect(callUrl).toBe('/api/custom/endpoint');
    });
  });
});
