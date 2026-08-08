/**
 * useTrackFingerprint hook tests (#2776)
 *
 * Tests API fetching, caching, polling, and error handling.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactNode, createElement } from 'react';
import { useTrackFingerprint } from '../useTrackFingerprint';

// Mock fetch
const setupFetch = (response: any, status = 200) => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(response),
  });
};

const mockFingerprintResponse = {
  track_id: 1,
  track_title: 'Test Track',
  artist: 'Test Artist',
  album: 'Test Album',
  fingerprint: {
    sub_bass: 0.15,
    bass: 0.20,
    low_mid: 0.18,
    mid: 0.22,
    high_mid: 0.10,
    presence: 0.08,
    brilliance: 0.07,
    lufs: -14.0,
    dynamic_range: 8.5,
    tempo_bpm: 120,
    spectral_centroid: 2500,
    spectral_complexity: 0.65,
    stereo_width: 0.8,
  },
};

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
}

describe('useTrackFingerprint', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should not fetch when trackId is null', () => {
    setupFetch(mockFingerprintResponse);

    renderHook(() => useTrackFingerprint(null), {
      wrapper: createWrapper(),
    });

    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('should not fetch when disabled', () => {
    setupFetch(mockFingerprintResponse);

    renderHook(() => useTrackFingerprint(1, { enabled: false }), {
      wrapper: createWrapper(),
    });

    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('should fetch fingerprint for valid trackId', async () => {
    setupFetch(mockFingerprintResponse);

    const { result } = renderHook(() => useTrackFingerprint(1), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.fingerprint).toBeTruthy();
    expect(result.current.trackTitle).toBe('Test Track');
    expect(result.current.artist).toBe('Test Artist');
    expect(result.current.error).toBeNull();
  });

  it('should set isPending when fingerprint not yet available (404)', async () => {
    setupFetch({ detail: 'Not found' }, 404);

    const { result } = renderHook(() => useTrackFingerprint(1), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // 404 means fingerprint is queued but not ready
    expect(result.current.fingerprint).toBeNull();
    expect(result.current.isPending).toBe(true);
  });

  it('should set error on non-404 failure', async () => {
    setupFetch({ detail: 'Server error' }, 500);

    const { result } = renderHook(() => useTrackFingerprint(1), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBeTruthy();
  });

  it('should not report isPending on a non-404 failure (#4847)', async () => {
    // Before the fix, a 500 collapsed into the same `data === null` state
    // as a genuine 404, so isPending stayed true and the caller had no way
    // to tell "queued" apart from "the endpoint is broken".
    setupFetch({ detail: 'Server error' }, 500);

    const { result } = renderHook(() => useTrackFingerprint(1), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBeTruthy();
    expect(result.current.isPending).toBe(false);
  });

  it('should not schedule another poll after a non-404 failure (#4847)', async () => {
    // Regression for the specific amplification bug: refetchInterval used
    // to key off `data === null` alone, which stays true after a failed
    // fetch that started from the "queued" state — polling forever
    // disguised as "pending" instead of surfacing the error once.
    setupFetch({ detail: 'Server error' }, 500);

    const { result } = renderHook(
      () => useTrackFingerprint(1, { retryInterval: 10 }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.error).toBeTruthy();
    });

    const callsAfterFirstFailure = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.length;

    // Wait comfortably past the (short, test-only) retry interval — if
    // polling were still scheduled, fetch would have been called again.
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect((global.fetch as ReturnType<typeof vi.fn>).mock.calls.length).toBe(
      callsAfterFirstFailure
    );
  });

  it('should keep polling on a genuine 404 (queued, not an error)', async () => {
    setupFetch({ detail: 'Not found' }, 404);

    const { result } = renderHook(
      () => useTrackFingerprint(1, { retryInterval: 10 }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isPending).toBe(true);
    });
    expect(result.current.error).toBeNull();

    const callsAfterFirstFetch = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.length;

    await waitFor(() => {
      expect((global.fetch as ReturnType<typeof vi.fn>).mock.calls.length).toBeGreaterThan(
        callsAfterFirstFetch
      );
    });
  });
});
