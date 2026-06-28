/**
 * useLibraryStats tests (#4185)
 *
 * Covers the includeStats gate, successful fetch, HTTP-error handling, and
 * abort-on-unmount.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useLibraryStats } from '../useLibraryStats';

let mockFetch: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  mockFetch = vi.fn();
  vi.stubGlobal('fetch', mockFetch);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('useLibraryStats (#4185)', () => {
  it('does not fetch when includeStats is false', async () => {
    const { result } = renderHook(() => useLibraryStats({ includeStats: false }));
    await act(async () => {
      await result.current.refetchStats();
    });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('fetches and stores stats on success', async () => {
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({ total_tracks: 10 }) });

    const { result } = renderHook(() => useLibraryStats({ includeStats: true }));
    await act(async () => {
      await result.current.refetchStats();
    });

    expect(mockFetch).toHaveBeenCalledWith('/api/library/stats', expect.objectContaining({ signal: expect.any(AbortSignal) }));
    expect(result.current.stats).toEqual({ total_tracks: 10 });
    expect(result.current.statsLoading).toBe(false);
    expect(result.current.statsError).toBeNull();
  });

  it('sets statsError on an HTTP error', async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 500 });

    const { result } = renderHook(() => useLibraryStats({ includeStats: true }));
    await act(async () => {
      await result.current.refetchStats();
    });

    expect(result.current.statsError).toContain('500');
    expect(result.current.statsLoading).toBe(false);
  });

  it('aborts the in-flight stats request on unmount', async () => {
    let signal: AbortSignal | undefined;
    mockFetch.mockImplementation((_url: string, opts: RequestInit) => {
      signal = opts.signal as AbortSignal;
      return new Promise(() => {});
    });

    const { result, unmount } = renderHook(() => useLibraryStats({ includeStats: true }));
    act(() => {
      void result.current.refetchStats();
    });
    expect(signal!.aborted).toBe(false);

    unmount();
    expect(signal!.aborted).toBe(true);
  });
});
