/**
 * useAlbumFingerprint hook tests (#2776)
 *
 * Tests single and batch album fingerprint fetching.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
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
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
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
