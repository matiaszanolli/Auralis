/**
 * useLibraryWithStats Hook Tests
 *
 * Tests for the library data + statistics composition hook.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';

// Mock useToast before importing hook
const mockSuccess = vi.fn();
const mockError = vi.fn();
const mockInfo = vi.fn();

vi.mock('@/components/shared/Toast', () => ({
  useToast: () => ({
    showToast: vi.fn(),
    success: mockSuccess,
    error: mockError,
    info: mockInfo,
    warning: vi.fn(),
  }),
}));

import { useLibraryWithStats } from '../useLibraryWithStats';

// Mock fetch
const mockFetch = vi.fn();

function makeTracksResponse(count: number, total: number, hasMore: boolean) {
  return {
    ok: true,
    json: () =>
      Promise.resolve({
        tracks: Array.from({ length: count }, (_, i) => ({
          id: i + 1,
          title: `Track ${i + 1}`,
          artist: 'Test Artist',
          album: 'Test Album',
          duration: 180,
          filepath: `/music/track${i + 1}.mp3`,
        })),
        total,
        has_more: hasMore,
      }),
  };
}

function makeStatsResponse() {
  return {
    ok: true,
    json: () =>
      Promise.resolve({
        total_tracks: 100,
        total_artists: 10,
        total_albums: 5,
        total_genres: 8,
        total_playlists: 3,
        total_duration: 36000,
        total_duration_formatted: '10:00:00',
        total_filesize: 5000000000,
        total_filesize_gb: 5.0,
        total_plays: 500,
        favorite_count: 25,
      }),
  };
}

describe('useLibraryWithStats', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
    vi.stubGlobal('fetch', mockFetch);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initial state', () => {
    it('starts with loading=true and empty tracks', () => {
      mockFetch.mockResolvedValue(makeTracksResponse(0, 0, false));

      const { result } = renderHook(() =>
        useLibraryWithStats({ view: 'all', autoLoad: false })
      );

      expect(result.current.tracks).toEqual([]);
      expect(result.current.stats).toBeNull();
      expect(result.current.hasMore).toBe(true);
    });
  });

  describe('autoLoad', () => {
    it('fetches tracks and stats on mount when autoLoad=true', async () => {
      mockFetch
        .mockResolvedValueOnce(makeTracksResponse(10, 50, true))
        .mockResolvedValueOnce(makeStatsResponse());

      const { result } = renderHook(() =>
        useLibraryWithStats({ view: 'all', autoLoad: true, includeStats: true })
      );

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.tracks).toHaveLength(10);
      expect(result.current.totalTracks).toBe(50);
      expect(result.current.hasMore).toBe(true);
    });

    it('does not fetch when autoLoad=false', () => {
      renderHook(() =>
        useLibraryWithStats({ view: 'all', autoLoad: false })
      );

      expect(mockFetch).not.toHaveBeenCalled();
    });
  });

  describe('fetchTracks', () => {
    it('uses favourites endpoint for favourites view', async () => {
      mockFetch.mockResolvedValue(makeTracksResponse(5, 5, false));

      const { result } = renderHook(() =>
        useLibraryWithStats({ view: 'favourites', autoLoad: false })
      );

      await act(async () => {
        await result.current.fetchTracks();
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/library/tracks/favorites'),
        expect.anything()  // fetch is called with (url, { signal }) — match the 2nd arg
      );
    });

    it('uses standard endpoint for all view', async () => {
      mockFetch.mockResolvedValue(makeTracksResponse(5, 5, false));

      const { result } = renderHook(() =>
        useLibraryWithStats({ view: 'all', autoLoad: false })
      );

      await act(async () => {
        await result.current.fetchTracks();
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringMatching(/\/api\/library\/tracks\?/),
        expect.anything()
      );
    });

    it('resets pagination on fetchTracks(true)', async () => {
      mockFetch.mockResolvedValue(makeTracksResponse(3, 3, false));

      const { result } = renderHook(() =>
        useLibraryWithStats({ view: 'all', autoLoad: false })
      );

      await act(async () => {
        await result.current.fetchTracks(true);
      });

      expect(result.current.offset).toBe(0);
      expect(result.current.tracks).toHaveLength(3);
    });

    it('sets error on fetch failure', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() =>
        useLibraryWithStats({ view: 'all', autoLoad: false })
      );

      await act(async () => {
        await result.current.fetchTracks();
      });

      expect(result.current.error).toBe('Failed to connect to server');
      expect(mockError).toHaveBeenCalledWith('Failed to connect to server');
    });

    it('sets error on non-ok response', async () => {
      mockFetch.mockResolvedValueOnce({ ok: false, status: 500 });

      const { result } = renderHook(() =>
        useLibraryWithStats({ view: 'all', autoLoad: false })
      );

      await act(async () => {
        await result.current.fetchTracks();
      });

      expect(result.current.error).toBe('Failed to load library');
    });

    it('prevents concurrent fetches', async () => {
      let resolveFirst: (v: any) => void;
      const slowResponse = new Promise((resolve) => {
        resolveFirst = resolve;
      });
      mockFetch.mockReturnValueOnce(slowResponse);

      const { result } = renderHook(() =>
        useLibraryWithStats({ view: 'all', autoLoad: false })
      );

      // Start first fetch
      let firstDone = false;
      act(() => {
        result.current.fetchTracks().then(() => { firstDone = true; });
      });

      // Try second fetch while first is in progress
      await act(async () => {
        await result.current.fetchTracks();
      });

      // Only one fetch call should have been made
      expect(mockFetch).toHaveBeenCalledTimes(1);

      // Cleanup: resolve the pending fetch
      resolveFirst!(makeTracksResponse(1, 1, false));
      await waitFor(() => expect(firstDone).toBe(true));
    });

    it('shows info toast when favourites view has no results', async () => {
      mockFetch.mockResolvedValueOnce(makeTracksResponse(0, 0, false));

      const { result } = renderHook(() =>
        useLibraryWithStats({ view: 'favourites', autoLoad: false })
      );

      await act(async () => {
        await result.current.fetchTracks(true);
      });

      expect(mockInfo).toHaveBeenCalledWith(
        expect.stringContaining('No favorites yet')
      );
    });
  });

  describe('loadMore', () => {
    it('appends tracks to existing list', async () => {
      // Initial fetch
      mockFetch.mockResolvedValueOnce(makeTracksResponse(50, 100, true));

      const { result } = renderHook(() =>
        useLibraryWithStats({ view: 'all', autoLoad: false })
      );

      await act(async () => {
        await result.current.fetchTracks();
      });

      expect(result.current.tracks).toHaveLength(50);

      // Load more
      mockFetch.mockResolvedValueOnce(makeTracksResponse(50, 100, false));

      await act(async () => {
        await result.current.loadMore();
      });

      await waitFor(() => {
        expect(result.current.isLoadingMore).toBe(false);
      });

      expect(result.current.tracks).toHaveLength(100);
    });
  });

  describe('loadMore offset advance (#3378 sibling regression)', () => {
    it('loadMore actually requests the NEXT page, not page 0 again', async () => {
      // Pre-fix sibling bug found while testing #3378: loadMore tried to
      // read the current offset synchronously via setOffset(prev => ...),
      // but React 18 doesn't run the updater synchronously, so newOffset
      // stayed 0 and loadMore re-fetched page 0. The existing "appends
      // tracks" test only checked tracks.length (50→100 with duplicate
      // pages from the mock), masking it.
      mockFetch.mockResolvedValueOnce(makeTracksResponse(50, 200, true));
      const { result } = renderHook(() =>
        useLibraryWithStats({ view: 'all', autoLoad: false })
      );

      await act(async () => {
        await result.current.fetchTracks();
      });

      mockFetch.mockResolvedValueOnce(makeTracksResponse(50, 200, true));
      await act(async () => {
        await result.current.loadMore();
      });
      await waitFor(() => {
        expect(result.current.tracks).toHaveLength(100);
      });

      // The second call (loadMore) must have asked for offset=50, not 0.
      const calls = mockFetch.mock.calls;
      const loadMoreUrl = calls[calls.length - 1]?.[0] as string;
      expect(loadMoreUrl).toContain('offset=50');
      expect(loadMoreUrl).not.toMatch(/[?&]offset=0(\b|&)/);
    });

    it('rapid loadMore calls are debounced and use the live offset (#2795)', async () => {
      // Pre-fix #2795 used setTimeout(0) + setOffset(prev => ...) to defer
      // the fetch — race-prone under rapid calls. Post-fix (per #3378 ref)
      // the fetchInProgressRef guard debounces and the offsetRef advances
      // consistently between fires.
      mockFetch.mockResolvedValueOnce(makeTracksResponse(50, 200, true));
      const { result } = renderHook(() =>
        useLibraryWithStats({ view: 'all', autoLoad: false })
      );

      await act(async () => {
        await result.current.fetchTracks();
      });

      // Fire 5 loadMore calls in rapid succession. The first acquires the
      // in-progress guard; the other four early-return. Only one network
      // request fires per advance.
      mockFetch.mockResolvedValueOnce(makeTracksResponse(50, 200, true));
      await act(async () => {
        await Promise.all([
          result.current.loadMore(),
          result.current.loadMore(),
          result.current.loadMore(),
          result.current.loadMore(),
          result.current.loadMore(),
        ]);
      });
      await waitFor(() => {
        expect(result.current.tracks).toHaveLength(100);
      });

      // initial fetch (1) + exactly ONE loadMore (1) = 2 total calls.
      expect(mockFetch).toHaveBeenCalledTimes(2);

      // The loadMore call used the live offset (50), not a stale value.
      const calls = mockFetch.mock.calls;
      const loadMoreUrl = calls[calls.length - 1]?.[0] as string;
      expect(loadMoreUrl).toContain('offset=50');
    });
  });

  describe('fetchTracks offset closure (#3378 regression)', () => {
    it('fetchTracks(false) uses the live offset, not a stale closure value', async () => {
      // Pre-fix: fetchTracks captured `offset` at definition time, so a call
      // to fetchTracks(false) AFTER loadMore advanced the offset would still
      // request `?offset=0`. Post-fix: it reads offsetRef.current and
      // requests the live value.
      mockFetch.mockResolvedValueOnce(makeTracksResponse(50, 200, true));
      const { result } = renderHook(() =>
        useLibraryWithStats({ view: 'all', autoLoad: false })
      );

      // Initial fetch — fills page 0
      await act(async () => {
        await result.current.fetchTracks();
      });

      // loadMore advances offset (existing passing test confirms tracks→100)
      mockFetch.mockResolvedValueOnce(makeTracksResponse(50, 200, true));
      await act(async () => {
        await result.current.loadMore();
      });
      await waitFor(() => {
        expect(result.current.tracks).toHaveLength(100);
      });

      // Now call fetchTracks(false) — the URL must request offset=50, not 0.
      mockFetch.mockResolvedValueOnce(makeTracksResponse(50, 200, true));
      await act(async () => {
        await result.current.fetchTracks(false);
      });

      const calls = mockFetch.mock.calls;
      const lastCallUrl = calls[calls.length - 1]?.[0] as string;
      expect(lastCallUrl).toContain('offset=50');
      // And explicitly: not still the stale offset=0
      expect(lastCallUrl).not.toMatch(/[?&]offset=0(\b|&)/);
    });

    it('fetchTracks(true) always requests offset=0 regardless of current offset', async () => {
      // Verifies the reset path still works after the closure fix.
      mockFetch.mockResolvedValueOnce(makeTracksResponse(50, 200, true));
      const { result } = renderHook(() =>
        useLibraryWithStats({ view: 'all', autoLoad: false })
      );

      await act(async () => {
        await result.current.fetchTracks();
      });

      mockFetch.mockResolvedValueOnce(makeTracksResponse(50, 200, true));
      await act(async () => {
        await result.current.loadMore();
      });
      await waitFor(() => {
        expect(result.current.tracks).toHaveLength(100);
      });

      // Reset: even with the live offset advanced, fetchTracks(true) → page 0
      mockFetch.mockResolvedValueOnce(makeTracksResponse(50, 200, true));
      await act(async () => {
        await result.current.fetchTracks(true);
      });

      const calls = mockFetch.mock.calls;
      const lastCallUrl = calls[calls.length - 1]?.[0] as string;
      expect(lastCallUrl).toMatch(/[?&]offset=0(\b|&)/);
    });
  });

  describe('refetchStats', () => {
    it('fetches library stats', async () => {
      mockFetch.mockResolvedValueOnce(makeStatsResponse());

      const { result } = renderHook(() =>
        useLibraryWithStats({ view: 'all', autoLoad: false, includeStats: true })
      );

      await act(async () => {
        await result.current.refetchStats();
      });

      expect(result.current.stats).toEqual(
        expect.objectContaining({ total_tracks: 100 })
      );
    });

    it('skips when includeStats=false', async () => {
      const { result } = renderHook(() =>
        useLibraryWithStats({ view: 'all', autoLoad: false, includeStats: false })
      );

      await act(async () => {
        await result.current.refetchStats();
      });

      expect(mockFetch).not.toHaveBeenCalled();
      expect(result.current.stats).toBeNull();
    });

    it('handles stats fetch failure gracefully (non-fatal)', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Stats error'));

      const { result } = renderHook(() =>
        useLibraryWithStats({ view: 'all', autoLoad: false, includeStats: true })
      );

      await act(async () => {
        await result.current.refetchStats();
      });

      // Should not set error — stats failure is non-fatal
      expect(result.current.error).toBeNull();
      expect(result.current.stats).toBeNull();
    });
  });

  describe('isElectron', () => {
    it('returns false when window.electronAPI is not defined', () => {
      const { result } = renderHook(() =>
        useLibraryWithStats({ view: 'all', autoLoad: false })
      );

      expect(result.current.isElectron()).toBe(false);
    });

    it('returns true when window.electronAPI exists', () => {
      window.electronAPI = { selectFolder: vi.fn() };

      const { result } = renderHook(() =>
        useLibraryWithStats({ view: 'all', autoLoad: false })
      );

      expect(result.current.isElectron()).toBe(true);

      window.electronAPI = undefined;
    });
  });

  describe('view changes', () => {
    it('refetches when view changes', async () => {
      mockFetch.mockResolvedValue(makeTracksResponse(5, 5, false));

      const { result, rerender } = renderHook(
        ({ view }) => useLibraryWithStats({ view, autoLoad: true }),
        { initialProps: { view: 'all' } }
      );

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      mockFetch.mockClear();
      mockFetch.mockResolvedValue(makeTracksResponse(2, 2, false));

      rerender({ view: 'favourites' });

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/favorites'),
          expect.anything()  // fetch is called with (url, { signal })
        );
      });
    });
  });
});
