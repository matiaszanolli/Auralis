/**
 * Library-wide fingerprint coverage hook — issue #4865
 *
 * `/api/library/fingerprints/status` and
 * `/api/similarity/fingerprint-queue/enqueue-all` were fully implemented —
 * coverage percentages, a display-ready status line, an ETA — and had no caller
 * anywhere in the frontend. This hook is that caller.
 *
 * The behaviours worth pinning are the ones that are easy to get wrong in a
 * polling hook: stopping once there is nothing left to do, not calling setState
 * after the settings dialog closes mid-request, and surfacing the backend's
 * error detail rather than a bare status line.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import {
  useFingerprintCoverage,
  POLL_INTERVAL_MS,
} from '../useFingerprintCoverage';

const status = (overrides: Record<string, unknown> = {}) => ({
  total_tracks: 1203,
  fingerprinted_tracks: 847,
  pending_tracks: 356,
  progress_percent: 70.4,
  status: '847 of 1203 tracks analysed',
  estimated_remaining_seconds: 10680,
  ...overrides,
});

const okResponse = (body: unknown) => ({
  ok: true,
  status: 200,
  json: () => Promise.resolve(body),
});

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('reading coverage', () => {
  it('maps the snake_case payload onto the camelCase shape', async () => {
    global.fetch = vi.fn().mockResolvedValue(okResponse(status()));

    const { result } = renderHook(() => useFingerprintCoverage());

    await waitFor(() => expect(result.current.coverage).not.toBeNull());
    expect(result.current.coverage).toEqual({
      totalTracks: 1203,
      fingerprintedTracks: 847,
      pendingTracks: 356,
      progressPercent: 70.4,
      status: '847 of 1203 tracks analysed',
      estimatedRemainingSeconds: 10680,
    });
  });

  it('reads the status endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue(okResponse(status()));
    global.fetch = fetchMock;

    renderHook(() => useFingerprintCoverage());

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(String(fetchMock.mock.calls[0][0])).toBe('/api/library/fingerprints/status');
  });

  it('does not fetch at all when disabled', () => {
    const fetchMock = vi.fn().mockResolvedValue(okResponse(status()));
    global.fetch = fetchMock;

    renderHook(() => useFingerprintCoverage(false));

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('surfaces the backend detail on failure', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      statusText: '',
      json: () => Promise.resolve({ detail: 'Library database is locked' }),
    });

    const { result } = renderHook(() => useFingerprintCoverage());

    await waitFor(() => expect(result.current.error).not.toBeNull());
    expect(result.current.error).toBe('Library database is locked');
  });
});

describe('polling', () => {
  /**
   * Fake timers and `waitFor` do not compose here — testing-library reaches for
   * `jest.advanceTimersByTime`, which vitest does not provide — so these flush
   * the initial fetch with `advanceTimersByTimeAsync(0)` instead, which runs
   * pending microtasks between ticks.
   */
  const settle = async () => {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
  };

  it('keeps polling while tracks are pending', async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn().mockResolvedValue(okResponse(status({ pending_tracks: 356 })));
    global.fetch = fetchMock;

    const { result } = renderHook(() => useFingerprintCoverage());
    await settle();
    expect(result.current.coverage).not.toBeNull();
    const afterFirstRead = fetchMock.mock.calls.length;

    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS + 1);
    });

    expect(fetchMock.mock.calls.length).toBeGreaterThan(afterFirstRead);
  });

  it('stops once nothing is pending', async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn().mockResolvedValue(
      okResponse(status({ pending_tracks: 0, progress_percent: 100 }))
    );
    global.fetch = fetchMock;

    const { result } = renderHook(() => useFingerprintCoverage());
    await settle();
    expect(result.current.coverage).not.toBeNull();
    const afterFirstRead = fetchMock.mock.calls.length;

    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 3);
    });

    // A fully-analysed library must not poll forever behind an open dialog.
    expect(fetchMock.mock.calls.length).toBe(afterFirstRead);
  });

  it('stops polling on unmount', async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn().mockResolvedValue(okResponse(status()));
    global.fetch = fetchMock;

    const { result, unmount } = renderHook(() => useFingerprintCoverage());
    await settle();
    expect(result.current.coverage).not.toBeNull();
    unmount();
    const afterUnmount = fetchMock.mock.calls.length;

    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 3);
    });

    expect(fetchMock.mock.calls.length).toBe(afterUnmount);
  });
});

describe('analyseRemaining', () => {
  it('posts to enqueue-all and then refreshes', async () => {
    const fetchMock = vi.fn().mockResolvedValue(okResponse(status()));
    global.fetch = fetchMock;

    const { result } = renderHook(() => useFingerprintCoverage());
    await waitFor(() => expect(result.current.coverage).not.toBeNull());
    fetchMock.mockClear();

    await act(async () => {
      await result.current.analyseRemaining();
    });

    const urls = fetchMock.mock.calls.map((c) => String(c[0]));
    expect(urls).toContain('/api/similarity/fingerprint-queue/enqueue-all');
    expect(urls).toContain('/api/library/fingerprints/status');
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'POST' });
  });

  it('refreshes even when the enqueue fails', async () => {
    // The queue depth may have changed regardless, and a stale card would
    // misreport it.
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(okResponse(status()))
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: '',
        json: () => Promise.resolve({ detail: 'queue unavailable' }),
      })
      .mockResolvedValue(okResponse(status()));
    global.fetch = fetchMock;

    const { result } = renderHook(() => useFingerprintCoverage());
    await waitFor(() => expect(result.current.coverage).not.toBeNull());

    await act(async () => {
      await result.current.analyseRemaining();
    });

    const urls = fetchMock.mock.calls.map((c) => String(c[0]));
    expect(urls.filter((u) => u === '/api/library/fingerprints/status').length).toBeGreaterThan(1);
  });

  it('clears the enqueueing flag on failure', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(okResponse(status()))
      .mockRejectedValueOnce(new Error('network down'))
      .mockResolvedValue(okResponse(status()));
    global.fetch = fetchMock;

    const { result } = renderHook(() => useFingerprintCoverage());
    await waitFor(() => expect(result.current.coverage).not.toBeNull());

    await act(async () => {
      await result.current.analyseRemaining();
    });

    expect(result.current.enqueueing).toBe(false);
  });
});
