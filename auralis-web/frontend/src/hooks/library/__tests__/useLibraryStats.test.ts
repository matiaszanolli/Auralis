/**
 * useLibraryStats Hook Tests
 *
 * Tests for library statistics fetching with abort controller support.
 *
 * @module hooks/library/__tests__/useLibraryStats.test
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useLibraryStats } from '../useLibraryStats';

describe('useLibraryStats', () => {
  let fetchSpy: any;

  const mockStats = {
    totalTracks: 1500,
    totalAlbums: 120,
    totalArtists: 85,
    totalDuration: 432000,
    totalSize: 50000000000,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    fetchSpy = vi.spyOn(globalThis, 'fetch') as any;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should start in loading state', () => {
    fetchSpy.mockReturnValue(new Promise(() => {})); // never resolves

    const { result } = renderHook(() => useLibraryStats());

    expect(result.current.isLoading).toBe(true);
    expect(result.current.stats).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('should fetch stats on mount', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockStats),
    } as Response);

    const { result } = renderHook(() => useLibraryStats());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.stats).toEqual(mockStats);
    expect(result.current.error).toBeNull();
    expect(fetchSpy).toHaveBeenCalledWith('/api/library/stats', expect.objectContaining({
      signal: expect.any(AbortSignal),
    }));
  });

  it('should handle HTTP error response', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: false,
      status: 500,
    } as Response);

    const { result } = renderHook(() => useLibraryStats());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.stats).toBeNull();
    expect(result.current.error).toBe('HTTP error! status: 500');
  });

  it('should handle network failure', async () => {
    fetchSpy.mockRejectedValueOnce(new Error('Network error'));

    const { result } = renderHook(() => useLibraryStats());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.stats).toBeNull();
    expect(result.current.error).toBe('Network error');
  });

  it('should handle non-Error thrown values', async () => {
    fetchSpy.mockRejectedValueOnce('string error');

    const { result } = renderHook(() => useLibraryStats());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.error).toBe('Failed to fetch stats');
  });

  it('should support refetch', async () => {
    const updatedStats = { ...mockStats, totalTracks: 1600 };

    fetchSpy
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockStats),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(updatedStats),
      } as Response);

    const { result } = renderHook(() => useLibraryStats());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.stats).toEqual(mockStats);

    await act(async () => {
      result.current.refetch();
    });

    await waitFor(() => expect(result.current.stats).toEqual(updatedStats));
  });

  it('should abort in-flight request on refetch', async () => {
    let abortSignals: AbortSignal[] = [];

    fetchSpy.mockImplementation((_url: any, init: any) => {
      abortSignals.push(init.signal);
      return new Promise((resolve) => {
        setTimeout(() => resolve({
          ok: true,
          json: () => Promise.resolve(mockStats),
        } as Response), 100);
      });
    });

    const { result } = renderHook(() => useLibraryStats());

    // Trigger refetch before first request completes
    await act(async () => {
      result.current.refetch();
    });

    // First request's signal should be aborted
    expect(abortSignals[0].aborted).toBe(true);
  });

  it('should abort request on unmount', async () => {
    let capturedSignal: AbortSignal | null = null;

    fetchSpy.mockImplementation((_url: any, init: any) => {
      capturedSignal = init.signal;
      return new Promise(() => {}); // never resolves
    });

    const { unmount } = renderHook(() => useLibraryStats());

    // Wait for effect to fire
    await act(async () => {});

    unmount();

    expect(capturedSignal!.aborted).toBe(true);
  });

  it('should ignore AbortError and not set error state', async () => {
    const abortError = new DOMException('The operation was aborted', 'AbortError');
    fetchSpy.mockRejectedValueOnce(abortError);

    const { result } = renderHook(() => useLibraryStats());

    // Flush microtasks to let the hook settle
    await act(async () => {});

    // AbortError should be silently ignored
    expect(result.current.error).toBeNull();
  });

  it('should clear error on successful refetch', async () => {
    fetchSpy
      .mockResolvedValueOnce({
        ok: false,
        status: 503,
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockStats),
      } as Response);

    const { result } = renderHook(() => useLibraryStats());

    await waitFor(() => expect(result.current.error).toBe('HTTP error! status: 503'));

    await act(async () => {
      result.current.refetch();
    });

    await waitFor(() => expect(result.current.error).toBeNull());
    expect(result.current.stats).toEqual(mockStats);
  });

  it('should return a stable refetch function', async () => {
    fetchSpy.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockStats),
    } as Response);

    const { result, rerender } = renderHook(() => useLibraryStats());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const refetchBefore = result.current.refetch;
    rerender();
    const refetchAfter = result.current.refetch;

    expect(refetchBefore).toBe(refetchAfter);
  });
});
