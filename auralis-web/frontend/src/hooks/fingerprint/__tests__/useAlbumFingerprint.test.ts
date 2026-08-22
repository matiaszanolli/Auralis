/**
 * useAlbumFingerprint hook tests (#2776)
 *
 * Tests single and batch album fingerprint fetching.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactNode, createElement } from 'react';
import { useAlbumFingerprint, useAlbumFingerprints } from '../useAlbumFingerprint';

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

  it('should fetch multiple album fingerprints', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockAlbumFpResponse),
    });

    const { result } = renderHook(() => useAlbumFingerprints([1, 2, 3]), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.fingerprints).toBeInstanceOf(Map);
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

  it('returns the successes when one album fails', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) =>
      Promise.resolve(
        String(url).includes('/2/') ? failure(500, 'boom') : {
          ok: true,
          status: 200,
          json: () => Promise.resolve(mockAlbumFpResponse),
        }
      )
    );

    const { result } = renderHook(() => useAlbumFingerprints([1, 2, 3]), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.fingerprints.size).toBe(3));
    // One bad album must not empty the grid — every tile still gets an entry,
    // and the failed one falls back to the hash gradient via null.
    expect(result.current.fingerprints.get(1)).toBeTruthy();
    expect(result.current.fingerprints.get(2)).toBeNull();
    expect(result.current.fingerprints.get(3)).toBeTruthy();
  });

  it('does not fail the whole batch query when an album errors', async () => {
    global.fetch = vi.fn().mockResolvedValue(failure(500, 'boom'));

    const { result } = renderHook(() => useAlbumFingerprints([1, 2]), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.error).toBeNull();
    expect(result.current.fingerprints.size).toBe(2);
  });

  it('logs the per-album failure that used to be invisible', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    global.fetch = vi.fn().mockResolvedValue(failure(500, 'boom'));

    const { result } = renderHook(() => useAlbumFingerprints([1]), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    // Pre-fix the 'rejected' branch was dead code: fetchAlbumFingerprint caught
    // its own errors and always fulfilled.
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });

  it('still resolves 404s to null without warning', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    global.fetch = vi.fn().mockResolvedValue(failure(404));

    const { result } = renderHook(() => useAlbumFingerprints([1, 2]), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.fingerprints.size).toBe(2));
    expect(result.current.fingerprints.get(1)).toBeNull();
    expect(warn).not.toHaveBeenCalled();
    warn.mockRestore();
  });
});
