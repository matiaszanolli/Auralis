/**
 * useLibraryPagination.loadMore error handling (#4173)
 *
 * loadMore previously had `if (response.ok) { ... }` with no else and a catch
 * that only console.error'd: on a transient 5xx it surfaced no error, fired no
 * toast, and left hasMore=true — so the infinite-scroll trigger re-fired into a
 * retry storm against a struggling server. These tests pin the mirrored
 * fetchTracks behaviour: error + toast set, hasMore cleared, retry storm stopped.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useLibraryPagination } from '../useLibraryPagination';
import { useToast } from '@/components/shared/Toast';

vi.mock('@/components/shared/Toast', () => ({ useToast: vi.fn() }));

const mockToastError = vi.fn();
let mockFetch: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(useToast).mockReturnValue({
    success: vi.fn(),
    error: mockToastError,
    info: vi.fn(),
  } as any);
  mockFetch = vi.fn();
  vi.stubGlobal('fetch', mockFetch);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('useLibraryPagination.loadMore (#4173)', () => {
  it('sets error + toast and clears hasMore on a non-OK (503) response', async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 503, statusText: 'Service Unavailable' });

    const { result } = renderHook(() => useLibraryPagination({ view: 'all' }));
    await act(async () => {
      await result.current.loadMore();
    });

    expect(result.current.error).toBe('Failed to load more tracks');
    expect(mockToastError).toHaveBeenCalledWith('Failed to load more tracks');
    // hasMore cleared so the scroll trigger does not retry-storm.
    expect(result.current.hasMore).toBe(false);
    expect(result.current.isLoadingMore).toBe(false);
  });

  it('sets error + clears hasMore on a network rejection', async () => {
    mockFetch.mockRejectedValue(new Error('network down'));

    const { result } = renderHook(() => useLibraryPagination({ view: 'all' }));
    await act(async () => {
      await result.current.loadMore();
    });

    expect(result.current.error).toBe('Failed to connect to server');
    expect(mockToastError).toHaveBeenCalledWith('Failed to connect to server');
    expect(result.current.hasMore).toBe(false);
  });

  it('stays silent when unmounted mid-loadMore (#5346)', async () => {
    // Post-#5346, loadMore is routed through get()/apiRequest.ts, which wraps
    // every rejection (including a raw AbortError) into an APIRequestError —
    // so a synthetic `mockRejectedValue(new DOMException(..., 'AbortError'))`
    // no longer reaches the hook with its name intact, and abort detection
    // now reads the request's own AbortController instead (see
    // useLibraryPagination.ts). Exercise the real mechanism: reject only
    // when the signal this request was actually given aborts.
    mockFetch.mockImplementation((_url: string, opts: RequestInit) => {
      return new Promise((_resolve, reject) => {
        opts.signal?.addEventListener('abort', () =>
          reject(new DOMException('The operation was aborted.', 'AbortError'))
        );
      });
    });

    const { result, unmount } = renderHook(() => useLibraryPagination({ view: 'all' }));
    let pending!: Promise<void>;
    act(() => {
      pending = result.current.loadMore();
    });

    unmount();
    await act(async () => {
      await pending;
    });

    expect(result.current.error).toBeNull();
    expect(mockToastError).not.toHaveBeenCalled();
  });

  it('advances offset and keeps hasMore on a successful load', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ tracks: [], has_more: true, total: 100 }),
    });

    const { result } = renderHook(() => useLibraryPagination({ view: 'all' }));
    await act(async () => {
      await result.current.loadMore();
    });

    expect(result.current.error).toBeNull();
    expect(result.current.hasMore).toBe(true);
    expect(result.current.offset).toBe(50);
    expect(mockToastError).not.toHaveBeenCalled();
  });
});

describe('useLibraryPagination.fetchTracks (#4185)', () => {
  it('fetches page 0 from the library endpoint and populates tracks (reset)', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        tracks: [{ id: 1, title: 'A' }, { id: 2, title: 'B' }],
        has_more: true,
        total: 2,
      }),
    });

    const { result } = renderHook(() => useLibraryPagination({ view: 'all' }));
    await act(async () => {
      await result.current.fetchTracks(true);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/library/tracks?limit=50&offset=0',
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );
    expect(result.current.tracks).toHaveLength(2);
    expect(result.current.totalTracks).toBe(2);
    expect(result.current.offset).toBe(0);
    expect(result.current.loading).toBe(false);
  });

  it('uses the favorites endpoint for the favourites view', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ tracks: [], has_more: false, total: 0 }),
    });

    const { result } = renderHook(() => useLibraryPagination({ view: 'favourites' }));
    await act(async () => {
      await result.current.fetchTracks(true);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/library/tracks/favorites?limit=50&offset=0',
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );
  });

  it('surfaces an error + toast when the initial fetch is not OK', async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 500, statusText: 'err' });

    const { result } = renderHook(() => useLibraryPagination({ view: 'all' }));
    await act(async () => {
      await result.current.fetchTracks(true);
    });

    expect(result.current.error).toBe('Failed to load library');
    expect(mockToastError).toHaveBeenCalledWith('Failed to load library');
  });

  it('aborts the in-flight fetch on unmount', async () => {
    let signal: AbortSignal | undefined;
    mockFetch.mockImplementation((_url: string, opts: RequestInit) => {
      signal = opts.signal as AbortSignal;
      return new Promise(() => {});
    });

    const { result, unmount } = renderHook(() => useLibraryPagination({ view: 'all' }));
    act(() => {
      void result.current.fetchTracks(true);
    });
    expect(signal!.aborted).toBe(false);

    unmount();
    expect(signal!.aborted).toBe(true);
  });
});

describe('useLibraryPagination track transform (#4830)', () => {
  it('surfaces genre from the backend genres array, not a nonexistent singular field', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        tracks: [
          { id: 1, title: 'A', album: 'Album A', duration: 100, artists: ['Artist A'], genres: ['Rock', 'Indie'] },
        ],
        has_more: false,
        total: 1,
      }),
    });

    const { result } = renderHook(() => useLibraryPagination({ view: 'all' }));
    await act(async () => {
      await result.current.fetchTracks(true);
    });

    expect(result.current.tracks[0].genre).toBe('Rock');
  });
});

describe('useLibraryPagination response-shape guard (#5346)', () => {
  it('surfaces an error instead of silently rendering an empty list when `tracks` is missing (initial fetch)', async () => {
    // The exact class of drift the guard exists to catch: a renamed/dropped
    // `tracks` key. Pre-fix, `data.tracks || []` swallowed this into a
    // silent empty library with no error and no toast.
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ total: 5, has_more: false }),
    });

    const { result } = renderHook(() => useLibraryPagination({ view: 'all' }));
    await act(async () => {
      await result.current.fetchTracks(true);
    });

    expect(result.current.tracks).toEqual([]);
    expect(result.current.error).toBe('Failed to load library');
    expect(mockToastError).toHaveBeenCalledWith('Failed to load library');
  });

  it('surfaces an error instead of silently rendering an empty page when `tracks` is missing (loadMore)', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ total: 5, has_more: true }),
    });

    const { result } = renderHook(() => useLibraryPagination({ view: 'all' }));
    await act(async () => {
      await result.current.loadMore();
    });

    expect(result.current.error).toBe('Failed to load more tracks');
    expect(mockToastError).toHaveBeenCalledWith('Failed to load more tracks');
    // Offset must not silently advance past a page that was never validated.
    expect(result.current.offset).toBe(0);
  });

  it('validates the favourites endpoint response the same way as the main list', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ tracks: 'not-an-array' }),
    });

    const { result } = renderHook(() => useLibraryPagination({ view: 'favourites' }));
    await act(async () => {
      await result.current.fetchTracks(true);
    });

    expect(result.current.error).toBe('Failed to load library');
  });
});

describe('useLibraryPagination request ownership (#4891)', () => {
  it('lets a view refresh supersede an in-flight loadMore and discards the stale page', async () => {
    let resolveStalePage!: (response: unknown) => void;
    const stalePage = new Promise((resolve) => {
      resolveStalePage = resolve;
    });

    mockFetch
      // Old "all" view loadMore. Deliberately ignores the abort signal so the
      // request-id guard, rather than the mock transport, must reject it.
      .mockImplementationOnce(() => stalePage)
      // New "favourites" view refresh.
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          tracks: [{ id: 2, title: 'Favourite track' }],
          has_more: false,
          total: 1,
        }),
      });

    const { result, rerender } = renderHook(
      ({ view }: { view: string }) => useLibraryPagination({ view }),
      { initialProps: { view: 'all' } }
    );

    let staleLoadMore!: Promise<void>;
    act(() => {
      staleLoadMore = result.current.loadMore();
    });
    expect(result.current.isLoadingMore).toBe(true);

    rerender({ view: 'favourites' });
    await act(async () => {
      await result.current.fetchTracks();
    });

    expect(mockFetch).toHaveBeenNthCalledWith(
      2,
      '/api/library/tracks/favorites?limit=50&offset=0',
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );
    expect(result.current.tracks.map((track) => track.title)).toEqual([
      'Favourite track',
    ]);

    await act(async () => {
      resolveStalePage({
        ok: true,
        json: async () => ({
          tracks: [{ id: 1, title: 'Stale all-view track' }],
          has_more: true,
          total: 100,
        }),
      });
      await staleLoadMore;
    });

    expect(result.current.tracks.map((track) => track.title)).toEqual([
      'Favourite track',
    ]);
    expect(result.current.offset).toBe(0);
    expect(result.current.hasMore).toBe(false);
    expect(result.current.totalTracks).toBe(1);
    expect(result.current.isLoadingMore).toBe(false);
  });
});
