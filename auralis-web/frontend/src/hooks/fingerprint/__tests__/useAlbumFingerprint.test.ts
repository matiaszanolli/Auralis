/**
 * useAlbumFingerprint hook tests (#2776)
 *
 * Tests single and batch album fingerprint fetching.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactNode, createElement } from 'react';
import { useAlbumFingerprint, useAlbumFingerprints } from '../useAlbumFingerprint';
import { DEFAULT_TIMEOUT_MS } from '@/utils/apiRequest';

const setupFetch = (response: any, status = 200) => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(response),
  });
};

const mockAlbumFpResponse = {
  album_id: 1,
  fingerprint: {
    sub_bass: 0.12,
    bass: 0.18,
    low_mid: 0.20,
    mid: 0.25,
    high_mid: 0.10,
    presence: 0.08,
    brilliance: 0.07,
    lufs: -12.0,
    dynamic_range: 10.0,
    tempo_bpm: 115,
    spectral_centroid: 2200,
    spectral_complexity: 0.55,
    stereo_width: 0.75,
  },
};

/** `GET /api/albums/fingerprints` answering every requested id (#5873). */
const batchFetch = () =>
  vi.fn().mockImplementation((url: string) => {
    const ids = new URL(String(url), 'http://x').searchParams.getAll('ids').map(Number);
    return Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({
        albums: ids.map((id) => ({ album_id: id, fingerprint: mockAlbumFpResponse.fingerprint })),
      }),
    });
  });

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
}

describe('useAlbumFingerprint', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should fetch album fingerprint', async () => {
    setupFetch(mockAlbumFpResponse);

    const { result } = renderHook(() => useAlbumFingerprint(1), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.fingerprint).toBeTruthy();
    expect(result.current.error).toBeNull();
  });

  it('should not fetch when disabled', () => {
    setupFetch(mockAlbumFpResponse);

    renderHook(() => useAlbumFingerprint(1, { enabled: false }), {
      wrapper: createWrapper(),
    });

    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('should handle 404 (no fingerprints)', async () => {
    setupFetch({ detail: 'Not found' }, 404);

    const { result } = renderHook(() => useAlbumFingerprint(1), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // 404 returns null fingerprint, not an error
    expect(result.current.fingerprint).toBeFalsy();
  });
});

describe('useAlbumFingerprints (batch)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches a page of albums in one batched request (#5873)', async () => {
    const fetchMock = batchFetch();
    global.fetch = fetchMock;

    const { result } = renderHook(() => useAlbumFingerprints([1, 2, 3]), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // One request for the page, not one per tile.
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const url = new URL(String(fetchMock.mock.calls[0][0]), 'http://x');
    expect(url.pathname).toBe('/api/albums/fingerprints');
    expect(url.searchParams.getAll('ids')).toEqual(['1', '2', '3']);
    expect(result.current.fingerprints.get(2)).toEqual(mockAlbumFpResponse.fingerprint);
    expect(result.current.error).toBeNull();
  });

  it('does not reorder the caller-owned albumIds array', () => {
    setupFetch(mockAlbumFpResponse);
    const albumIds = [3, 1, 2];
    const originalReference = albumIds;

    renderHook(() => useAlbumFingerprints(albumIds), {
      wrapper: createWrapper(),
    });

    expect(albumIds).toBe(originalReference);
    expect(albumIds).toEqual([3, 1, 2]);
  });

  it('should handle empty albumIds array', async () => {
    const { result } = renderHook(() => useAlbumFingerprints([]), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.fingerprints.size).toBe(0);
  });

  it('adds a scroll page without refetching cached albums or blanking the map (#5611)', async () => {
    const fetchMock = batchFetch();
    global.fetch = fetchMock;

    const { result, rerender } = renderHook(
      ({ ids }: { ids: number[] }) => useAlbumFingerprints(ids),
      { wrapper: createWrapper(), initialProps: { ids: [1, 2, 3] } }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // Infinite scroll delivers two more albums. Cached albums must neither be
    // refetched nor vanish from the map while the new queries run — the old
    // whole-list key refetched everything and returned an empty Map, blanking
    // every tile's fingerprint colouring on each page.
    rerender({ ids: [1, 2, 3, 4, 5] });
    expect(result.current.fingerprints.get(1)).toBeTruthy();
    expect(result.current.fingerprints.get(2)).toBeTruthy();
    expect(result.current.fingerprints.get(3)).toBeTruthy();

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
    // The new page is one more request, carrying only the uncached ids.
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(new URL(String(fetchMock.mock.calls[1][0]), 'http://x').searchParams.getAll('ids'))
      .toEqual(['4', '5']);
    expect(result.current.fingerprints.get(4)).toBeTruthy();
    expect(result.current.fingerprints.get(5)).toBeTruthy();
  });
});

/**
 * #5122: error propagation — the sibling half of #4847.
 *
 * `fetchAlbumFingerprint` wrapped its own `throw` in a `try/catch` that turned
 * every failure — 5xx, network drop, backend exception — back into `null`, so a
 * broken endpoint was indistinguishable from "this album has no fingerprint
 * yet": the queryFn never rejected, leaving `query.error` permanently
 * `undefined` and `query.isError` permanently `false`.
 *
 * The cost was not only diagnosability. The app configures `retry: 1`, and a
 * resolved `null` is a *success* — so a transient 500 was cached for the
 * 5-minute staleTime and never retried, where a rejection would have been.
 */
const failure = (status: number, detail?: string) => ({
  ok: false,
  status,
  statusText: '',
  json: () =>
    detail ? Promise.resolve({ detail }) : Promise.reject(new Error('not json')),
});

describe('useAlbumFingerprint error propagation (#5122)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('populates query.error on a 500', async () => {
    global.fetch = vi.fn().mockResolvedValue(failure(500, 'fingerprint store unavailable'));

    const { result } = renderHook(() => useAlbumFingerprint(7), {
      wrapper: createWrapper(),
    });

    // Pre-fix: isError stayed false forever and the fingerprint resolved to null.
    await waitFor(() => expect(result.current.error).toBeTruthy());
    expect((result.current.error as Error).message).toBe('fingerprint store unavailable');
  });

  it('propagates a network-level failure too', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Failed to fetch'));

    const { result } = renderHook(() => useAlbumFingerprint(7), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.error).toBeTruthy());
  });

  it('still resolves a 404 to null with no error', async () => {
    global.fetch = vi.fn().mockResolvedValue(failure(404));

    const { result } = renderHook(() => useAlbumFingerprint(7), {
      wrapper: createWrapper(),
    });

    // The hash-gradient fallback path must be preserved exactly.
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    // The hook maps a null fingerprint to `undefined` (`query.data ?? undefined`).
    expect(result.current.fingerprint).toBeUndefined();
    expect(result.current.error).toBeFalsy();
  });
});

describe('useAlbumFingerprints batch tolerance (#5122)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('an album absent from the batch answer is null, not an error (#5873)', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({
        albums: [1, 3].map((id) => ({ album_id: id, fingerprint: mockAlbumFpResponse.fingerprint })),
      }),
    });

    const { result } = renderHook(() => useAlbumFingerprints([1, 2, 3]), {
      wrapper: createWrapper(),
    });

    // Album 2 has no fingerprint yet: the hash-gradient fallback, like a 404
    // on the single-album route.
    await waitFor(() => expect(result.current.fingerprints.get(1)).toBeTruthy());
    expect(result.current.fingerprints.get(2)).toBeNull();
    expect(result.current.fingerprints.get(3)).toBeTruthy();
    expect(result.current.error).toBeNull();
  });

  it('surfaces a failing album as an error without taking down the map (#5611)', async () => {
    global.fetch = vi.fn().mockResolvedValue(failure(500, 'boom'));

    const { result } = renderHook(() => useAlbumFingerprints([1, 2]), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    // A failed batch fails each album's query: the error is visible on the
    // hook, and the map still carries every requested id (failed albums as
    // null → hash-gradient fallback per tile).
    expect(result.current.error).not.toBeNull();
    expect(result.current.fingerprints.size).toBe(2);
    expect(result.current.fingerprints.get(1)).toBeNull();
    expect(result.current.fingerprints.get(2)).toBeNull();
  });

  it('exposes a per-album failure as query error instead of swallowing it', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    global.fetch = vi.fn().mockResolvedValue(failure(500, 'boom'));

    const { result } = renderHook(() => useAlbumFingerprints([1]), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    // Pre-#5122 the failure was invisible (resolved to null). The per-album
    // query now rejects, so the failure is observable as an error.
    expect(result.current.error).not.toBeNull();
    expect(warn).not.toHaveBeenCalled();
    warn.mockRestore();
  });

});

/**
 * #5019: both fingerprint fetchers used a bare fetch() with no signal and no
 * timeout, so a stalled backend left the query loading forever — and an album
 * grid issues one request per visible tile.
 */
describe('request timeout (#5019)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('bounds the request and surfaces the timeout as an error', async () => {
    vi.useFakeTimers();
    try {
      let captured: AbortSignal | undefined;
      global.fetch = vi.fn((_url: string, init: RequestInit) => {
        captured = init.signal as AbortSignal;
        return new Promise((_resolve, reject) => {
          init.signal?.addEventListener('abort', () => {
            reject(Object.assign(new Error('aborted'), { name: 'AbortError' }));
          });
        });
      }) as unknown as typeof fetch;

      const { result } = renderHook(() => useAlbumFingerprint(4242), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await vi.advanceTimersByTimeAsync(1);
      });
      // The bare fetch() passed no signal at all; the shared transport always
      // does, and aborts it once DEFAULT_TIMEOUT_MS elapses.
      expect(captured).toBeDefined();
      expect(captured!.aborted).toBe(false);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(DEFAULT_TIMEOUT_MS);
      });

      expect(captured!.aborted).toBe(true);
      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });
});

// ----------------------------------------------------------------------------
// Single-hook query signal forwarding (#6221 / #5650)
// ----------------------------------------------------------------------------

describe('useAlbumFingerprint signal forwarding (#6221)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('aborts the in-flight fetch when the hook unmounts', async () => {
    // A fetch that never resolves on its own: only an abort can end it.
    let captured: AbortSignal | null | undefined;
    global.fetch = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
      captured = init?.signal;
      return new Promise<Response>((_resolve, reject) => {
        captured?.addEventListener('abort', () =>
          reject(new DOMException('Aborted', 'AbortError'))
        );
      });
    });

    const { unmount } = renderHook(() => useAlbumFingerprint(42), {
      wrapper: createWrapper(),
    });

    // The queryFn must have forwarded its signal to the transport by now.
    await waitFor(() => expect(captured).toBeDefined());
    expect(captured!.aborted).toBe(false);

    unmount();

    // React Query aborts the query on unmount; the forwarded signal must trip.
    await waitFor(() => expect(captured!.aborted).toBe(true));
  });
});

describe('useAlbumFingerprints cancellation (#5650)', () => {
  const hangingFetch = (signals: AbortSignal[]) =>
    vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
      const signal = init?.signal;
      if (signal) signals.push(signal);
      return new Promise<Response>((_resolve, reject) => {
        signal?.addEventListener('abort', () =>
          reject(new DOMException('Aborted', 'AbortError'))
        );
      });
    });

  it('aborts the batch request once every album in it is cancelled (#5873)', async () => {
    const signals: AbortSignal[] = [];
    global.fetch = hangingFetch(signals);

    const ids = Array.from({ length: 14 }, (_, i) => 1000 + i);
    const { unmount } = renderHook(() => useAlbumFingerprints(ids), { wrapper: createWrapper() });

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    expect(signals[0].aborted).toBe(false);

    unmount();
    await waitFor(() => expect(signals[0].aborted).toBe(true));
  });

  it('issues no request for batches cancelled while they waited for a slot', async () => {
    // 450 albums = 5 batches of <=100 against a 4-request gate: 4 start and
    // hang until aborted, 1 waits for a slot. Unmounting cancels all of them;
    // the waiting batch must wake, see the abort, and never reach fetch.
    const signals: AbortSignal[] = [];
    global.fetch = hangingFetch(signals);

    const ids = Array.from({ length: 450 }, (_, i) => 2000 + i);
    const { unmount } = renderHook(() => useAlbumFingerprints(ids), { wrapper: createWrapper() });

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(4));

    unmount();
    await waitFor(() => expect(signals.every((s) => s.aborted)).toBe(true));
    // Let the released slots wake the waiter.
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(global.fetch).toHaveBeenCalledTimes(4);
  });
});
