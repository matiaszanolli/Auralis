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

  it('stays silent on AbortError (no error, no toast)', async () => {
    mockFetch.mockRejectedValue(new DOMException('aborted', 'AbortError'));

    const { result } = renderHook(() => useLibraryPagination({ view: 'all' }));
    await act(async () => {
      await result.current.loadMore();
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
