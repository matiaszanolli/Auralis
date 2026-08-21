/**
 * useSimilarTracks hook tests (#2776)
 *
 * Tests similarity search, caching, validation, and race conditions.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useSimilarTracks } from '../useSimilarTracks';

// Mock fetch
const mockFetchResponse = (data: any, ok = true, status = 200) => {
  global.fetch = vi.fn().mockResolvedValue({
    ok,
    status,
    json: () => Promise.resolve(data),
  });
};

const mockSimilarResponse = [
  {
    track_id: 2,
    distance: 0.15,
    similarity_score: 0.85,
    rank: 1,
    title: 'Similar Track 1',
    artist: 'Artist A',
    album: 'Album X',
  },
  {
    track_id: 3,
    distance: 0.30,
    similarity_score: 0.70,
    rank: 2,
    title: 'Similar Track 2',
    artist: 'Artist B',
    album: 'Album Y',
  },
];

describe('useSimilarTracks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should return null similarTracks initially', () => {
    const { result } = renderHook(() => useSimilarTracks());

    expect(result.current.similarTracks).toBeNull();
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('should fetch similar tracks and map snake_case to camelCase', async () => {
    mockFetchResponse(mockSimilarResponse);

    const { result } = renderHook(() => useSimilarTracks());

    let tracks: any;
    await act(async () => {
      tracks = await result.current.findSimilar(1);
    });

    expect(tracks).toHaveLength(2);
    expect(tracks[0].trackId).toBe(2);
    expect(tracks[0].similarityScore).toBe(0.85);
    expect(tracks[0].title).toBe('Similar Track 1');

    expect(result.current.similarTracks).toHaveLength(2);
    expect(result.current.loading).toBe(false);
  });

  it('should return cached results on second call with same params', async () => {
    mockFetchResponse(mockSimilarResponse);

    const { result } = renderHook(() => useSimilarTracks());

    await act(async () => {
      await result.current.findSimilar(1, { limit: 10 });
    });

    // Reset fetch mock to verify it's not called again
    (global.fetch as any).mockClear();

    await act(async () => {
      await result.current.findSimilar(1, { limit: 10 });
    });

    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('should set error on failed fetch', async () => {
    mockFetchResponse({ detail: 'Not found' }, false, 404);

    const { result } = renderHook(() => useSimilarTracks());

    await act(async () => {
      try {
        await result.current.findSimilar(999);
      } catch {
        // Expected
      }
    });

    expect(result.current.error).toBeTruthy();
    expect(result.current.loading).toBe(false);
  });

  it('should throw on invalid limit', async () => {
    const { result } = renderHook(() => useSimilarTracks());

    await expect(
      act(async () => {
        await result.current.findSimilar(1, { limit: 0 });
      })
    ).rejects.toThrow();
  });

  it('should clear results', async () => {
    mockFetchResponse(mockSimilarResponse);

    const { result } = renderHook(() => useSimilarTracks());

    await act(async () => {
      await result.current.findSimilar(1);
    });

    expect(result.current.similarTracks).not.toBeNull();

    act(() => {
      result.current.clear();
    });

    expect(result.current.similarTracks).toBeNull();
    expect(result.current.error).toBeNull();
  });
});

/**
 * #4626: the backend's `detail` body must survive the fetch boundary.
 *
 * `useSimilarTracks` threw `Similarity search failed: ${status} ${statusText}`
 * without ever reading the body, so the router's deliberately-actionable detail
 * was discarded irrecoverably (the body can only be read once, and only before
 * the error propagates). `statusText` is also empty over HTTP/2, which made the
 * message degrade to `"Similarity search failed: 404 "`.
 */
describe('backend error detail (#4626)', () => {
  const mockErrorResponse = (status: number, detail: string, statusText = '') => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status,
      statusText,
      json: () => Promise.resolve({ detail }),
    });
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('surfaces the queued-for-fingerprinting detail rather than the status line', async () => {
    const detail =
      'Track 7 does not have a fingerprint. Queued for background processing.';
    mockErrorResponse(404, detail);

    const { result } = renderHook(() => useSimilarTracks());
    await act(async () => {
      await result.current.findSimilar(7).catch(() => {});
    });

    expect(result.current.error).toBe(detail);
    expect(result.current.errorStatus).toBe(404);
  });

  it('exposes the status so a 503 is distinguishable from a 404', async () => {
    mockErrorResponse(503, 'Similarity system not initialized.');

    const { result } = renderHook(() => useSimilarTracks());
    await act(async () => {
      await result.current.findSimilar(7).catch(() => {});
    });

    expect(result.current.errorStatus).toBe(503);
  });

  it('stays informative when statusText is empty (the HTTP/2 shape)', async () => {
    mockErrorResponse(404, 'Track 7 not found', '');

    const { result } = renderHook(() => useSimilarTracks());
    await act(async () => {
      await result.current.findSimilar(7).catch(() => {});
    });

    // Previously: "Similarity search failed: 404 " — a string with no content.
    expect(result.current.error).toBe('Track 7 not found');
  });

  it('falls back to the status line when the body carries no detail', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: () => Promise.reject(new Error('not json')),
    });

    const { result } = renderHook(() => useSimilarTracks());
    await act(async () => {
      await result.current.findSimilar(7).catch(() => {});
    });

    expect(result.current.error).toBe('HTTP 500: Internal Server Error');
    expect(result.current.errorStatus).toBe(500);
  });

  it('clears the status alongside the message', async () => {
    mockErrorResponse(404, 'Track 7 not found');

    const { result } = renderHook(() => useSimilarTracks());
    await act(async () => {
      await result.current.findSimilar(7).catch(() => {});
    });
    expect(result.current.errorStatus).toBe(404);

    act(() => {
      result.current.clear();
    });
    expect(result.current.error).toBeNull();
    expect(result.current.errorStatus).toBeNull();
  });
});
