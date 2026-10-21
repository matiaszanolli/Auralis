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

    // Load two pages (100 tracks of 120).
    mockFetch
      .mockResolvedValueOnce(page([1, 2], true, 120))
      .mockResolvedValueOnce(page([3, 4], true, 120));
    await act(async () => {
      await result.current.fetchTracks();
    });
    await act(async () => {
      await result.current.loadMore();
    });
    expect(result.current.tracks).toHaveLength(4);

    // The refresh pages carry server-side changes: track 2 was deleted,
    // and every surviving title changed.
    mockFetch
      .mockResolvedValueOnce(page([1, 3], true, 120, 'Updated'))
      .mockResolvedValueOnce(page([4, 5], false, 120, 'Updated'));

    await act(async () => {
      await result.current.refreshTracks();
    });

    const tracks = result.current.tracks;
    expect(tracks).toHaveLength(4);
    expect(idsOf(tracks)).toEqual([1, 3, 4, 5]);
    // Replaced wholesale — no duplicates from append-style merging.
    expect(new Set(idsOf(tracks)).size).toBe(4);
    expect(tracks[0].title).toBe('Updated 1');
    // Pagination continuity: the refresh consumed two pages, loadMore
    // continues from there.
    expect(result.current.offset).toBe(100);
    expect(result.current.hasMore).toBe(false);
    expect(result.current.totalTracks).toBe(120);
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
