/**
 * useLibraryPagination.refreshTracks — in-place refetch (#5626)
 *
 * Post-mutation refreshes went through fetchTracks(), which empties the
 * list, raises the full-screen `loading`, and drops everything past page 1:
 * favouriting a track at row 3,000 snapped the view back to a 50-item list.
 * refreshTracks re-fetches exactly the loaded pages, replaces the array
 * wholesale (never appends — no duplicates), and never touches `loading`,
 * so the list stays mounted and the old rows ride out the request.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useLibraryPagination } from '../useLibraryPagination';
import { useToast } from '@/components/shared/Toast';

vi.mock('@/components/shared/Toast', () => ({ useToast: vi.fn() }));

const apiTrack = (id: number, title = `Track ${id}`) => ({
  id,
  title,
  artist: 'Artist',
  album: 'Album',
  duration: 100,
});

/** A /api/library/tracks page the transport can resolve. */
const page = (ids: number[], hasMore: boolean, total: number, titlePrefix = 'Track') => ({
  ok: true,
  status: 200,
  json: async () => ({
    tracks: ids.map((id) => apiTrack(id, `${titlePrefix} ${id}`)),
    has_more: hasMore,
    total,
  }),
});

/** A server holding `ids`, answering /api/library/tracks by its real limit/offset contract. */
function serve(ids: number[], titlePrefix = 'Track') {
  return (url: unknown) => {
    const params = new URL(String(url), 'http://x').searchParams;
    const limit = Number(params.get('limit'));
    const offset = Number(params.get('offset'));
    return Promise.resolve(page(ids.slice(offset, offset + limit), offset + limit < ids.length, ids.length, titlePrefix));
  };
}

const range = (from: number, count: number) => Array.from({ length: count }, (_, i) => from + i);

/** A fetch promise the test settles by hand, for mid-refresh assertions. */
function deferredPage(p: () => ReturnType<typeof page>) {
  let resolve!: (value: unknown) => void;
  const promise = new Promise((res) => {
    resolve = res;
  });
  return {
    promise,
    settle: () => resolve(p()),
  };
}

let mockFetch: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(useToast).mockReturnValue({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  } as any);
  mockFetch = vi.fn();
  vi.stubGlobal('fetch', mockFetch);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const idsOf = (tracks: { id: number }[]) => tracks.map((t) => t.id);

describe('useLibraryPagination.refreshTracks (#5626)', () => {
  it('replaces loaded pages in place: never empties, never appends', async () => {
    const { result } = renderHook(() => useLibraryPagination({ view: 'all' }));

    // Load two pages (rows 1-100 of 120).
    mockFetch.mockImplementation(serve(range(1, 120)));
    await act(async () => {
      await result.current.fetchTracks();
    });
    await act(async () => {
      await result.current.loadMore();
    });
    expect(result.current.tracks).toHaveLength(100);

    // The server changed: track 2 was deleted, and every surviving title changed.
    mockFetch.mockImplementation(serve(range(1, 120).filter((id) => id !== 2), 'Updated'));
    await act(async () => {
      await result.current.refreshTracks();
    });

    const tracks = result.current.tracks;
    expect(tracks).toHaveLength(100);
    expect(idsOf(tracks)).toEqual(range(1, 120).filter((id) => id !== 2).slice(0, 100));
    // Replaced wholesale - no duplicates from append-style merging.
    expect(new Set(idsOf(tracks)).size).toBe(100);
    expect(tracks[0].title).toBe('Updated 1');
    // Pagination continuity: the last loaded page starts at 50, loadMore continues at 100.
    expect(result.current.offset).toBe(50);
    expect(result.current.hasMore).toBe(true);
    expect(result.current.totalTracks).toBe(119);
  });

  it('loadMore after a refresh continues at the next unloaded page, not one past it', async () => {
    const { result } = renderHook(() => useLibraryPagination({ view: 'all' }));
    const requested = () =>
      mockFetch.mock.calls.map((call) => new URL(String(call[0]), 'http://x').searchParams.get('offset'));

    mockFetch.mockImplementation(serve(range(1, 300)));
    await act(async () => {
      await result.current.fetchTracks();
    });
    await act(async () => {
      await result.current.loadMore();
    });
    expect(result.current.offset).toBe(50);

    await act(async () => {
      await result.current.refreshTracks();
    });
    expect(result.current.tracks).toHaveLength(100);
    expect(result.current.offset).toBe(50); // the last LOADED page, same as before the refresh

    await act(async () => {
      await result.current.loadMore();
    });

    // 100 is the first row nobody has loaded; 150 would silently skip rows 101-150.
    expect(requested().slice(-1)).toEqual(['100']);
    expect(idsOf(result.current.tracks)).toEqual(range(1, 150));
  });

  it('refreshing many loaded pages takes a bounded number of requests (#5902)', async () => {
    const { result } = renderHook(() => useLibraryPagination({ view: 'all' }));

    mockFetch.mockImplementation(serve(range(1, 1000)));
    await act(async () => {
      await result.current.fetchTracks();
    });
    for (let i = 0; i < 9; i += 1) {
      await act(async () => {
        await result.current.loadMore();
      });
    }
    expect(result.current.tracks).toHaveLength(500); // ten pages loaded

    mockFetch.mockClear();
    await act(async () => {
      await result.current.refreshTracks();
    });

    expect(result.current.tracks).toHaveLength(500);
    expect(mockFetch).toHaveBeenCalledTimes(3); // 200 + 200 + 100 rows, not ten 50-row requests
    expect(result.current.offset).toBe(450);
  });

  it('never empties the list or raises `loading` while the refresh is in flight', async () => {
    const { result } = renderHook(() => useLibraryPagination({ view: 'all' }));

    mockFetch
      .mockResolvedValueOnce(page([1, 2], false, 2))
      .mockResolvedValueOnce(page([9, 10], false, 2));
    await act(async () => {
      await result.current.fetchTracks();
    });
    expect(result.current.tracks).toHaveLength(2);

    // Hang the first refresh page; the populated list must ride it out.
    const pending = deferredPage(() => page([9, 10], false, 2));
    mockFetch.mockReturnValueOnce(pending.promise);

    let refreshPromise!: Promise<void>;
    act(() => {
      refreshPromise = result.current.refreshTracks();
    });

    // Mid-refresh: same rows, still mounted, and `loading` untouched —
    // the skeleton gate must not fire.
    expect(result.current.tracks).toHaveLength(2);
    expect(idsOf(result.current.tracks)).toEqual([1, 2]);
    expect(result.current.loading).toBe(false);

    await act(async () => {
      pending.settle();
      await refreshPromise;
    });
    expect(idsOf(result.current.tracks)).toEqual([9, 10]);
  });

  it('keeps the old list and surfaces the toast on a failed refresh', async () => {
    const { result } = renderHook(() => useLibraryPagination({ view: 'all' }));

    mockFetch.mockResolvedValueOnce(page([1, 2], false, 2));
    await act(async () => {
      await result.current.fetchTracks();
    });

    mockFetch.mockResolvedValueOnce({ ok: false, status: 503, statusText: 'Service Unavailable' });
    await act(async () => {
      await result.current.refreshTracks();
    });

    expect(idsOf(result.current.tracks)).toEqual([1, 2]);
    expect(result.current.error).toBe('Failed to refresh library');
  });

  it('delegates to the initial-load path when the list is empty', async () => {
    const { result } = renderHook(() => useLibraryPagination({ view: 'all' }));

    mockFetch.mockResolvedValueOnce(page([1, 2], false, 2));
    await act(async () => {
      await result.current.refreshTracks();
    });

    // fetchTracks(true) semantics: loading raised and rows landed.
    expect(result.current.tracks).toHaveLength(2);
    expect(result.current.loading).toBe(false);
  });
});
