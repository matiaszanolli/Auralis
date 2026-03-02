/**
 * useLibraryData – artwork_url field mapping tests (issue #2386)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Track.to_dict() returns artwork under 'artwork_url'.  The frontend
 * transformer previously read 'album_art || albumArt', neither of which
 * is present in the response, so albumArt was always undefined.
 *
 * Acceptance criteria:
 *  - albumArt is populated from artwork_url in the initial fetch
 *  - albumArt is populated from artwork_url in the loadMore fetch
 *  - Legacy names (album_art, albumArt) still work as fallbacks
 *
 * Strategy:
 *  - Stub global.fetch per-test so the hook receives exactly the response
 *    shape we want (mirrors what the backend returns after the rename).
 *  - Mock useToast (notification side-effects only).
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, afterEach, vi } from 'vitest';
import { useLibraryData } from '../useLibraryData';

// ============================================================================
// Mock useToast — only used for UI notifications, irrelevant to field mapping
// ============================================================================

// Stable references — re-creating vi.fn() on every useToast() call would
// change the success/error/info deps of useCallback(fetchTracks) on each
// render, causing an infinite re-render loop and OOM.
vi.mock('@/components/shared/Toast', () => {
  const toastMethods = {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  };
  return { useToast: () => toastMethods };
});

// ============================================================================
// Helpers
// ============================================================================

function makeTrack(overrides: Record<string, any> = {}) {
  return {
    id: 1,
    title: 'Test Track',
    artist: 'Test Artist',
    album: 'Test Album',
    duration: 240,
    ...overrides,
  };
}

/** Build a fake Response object from a plain object. */
function fakeJsonResponse(body: object, ok = true): Response {
  return {
    ok,
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

/** Stub global.fetch to return a single response. */
function stubFetch(response: Response) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response));
}

/** Stub global.fetch with a sequence of responses (one per call). */
function stubFetchSequence(responses: Response[]) {
  const mock = vi.fn();
  responses.forEach(r => mock.mockResolvedValueOnce(r));
  vi.stubGlobal('fetch', mock);
}

// ============================================================================
// Tests
// ============================================================================

describe('useLibraryData – albumArt field mapping (issue #2386)', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  // --------------------------------------------------------------------------
  // Initial fetch (fetchTracks)
  // --------------------------------------------------------------------------

  it('maps artwork_url to albumArt on initial fetch', async () => {
    stubFetch(fakeJsonResponse({
      tracks: [makeTrack({ artwork_url: '/art/cover.jpg' })],
      total: 1,
      has_more: false,
    }));

    const { result } = renderHook(() =>
      useLibraryData({ view: 'all', autoLoad: true }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.tracks[0].albumArt).toBe('/art/cover.jpg');
  });

  it('artwork_url takes priority over legacy album_art on initial fetch', async () => {
    stubFetch(fakeJsonResponse({
      tracks: [makeTrack({ artwork_url: '/art/new.jpg', album_art: '/art/old.jpg' })],
      total: 1,
      has_more: false,
    }));

    const { result } = renderHook(() =>
      useLibraryData({ view: 'all', autoLoad: true }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.tracks[0].albumArt).toBe('/art/new.jpg');
  });

  it('falls back to album_art when artwork_url is absent', async () => {
    stubFetch(fakeJsonResponse({
      tracks: [makeTrack({ album_art: '/art/legacy.jpg' })],
      total: 1,
      has_more: false,
    }));

    const { result } = renderHook(() =>
      useLibraryData({ view: 'all', autoLoad: true }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.tracks[0].albumArt).toBe('/art/legacy.jpg');
  });

  it('albumArt is falsy when no artwork field is present', async () => {
    stubFetch(fakeJsonResponse({
      tracks: [makeTrack()],  // no artwork fields
      total: 1,
      has_more: false,
    }));

    const { result } = renderHook(() =>
      useLibraryData({ view: 'all', autoLoad: true }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.tracks[0].albumArt).toBeFalsy();
  });

  it('maps artwork_url for every track in a multi-track response', async () => {
    stubFetch(fakeJsonResponse({
      tracks: [
        makeTrack({ id: 1, artwork_url: '/art/1.jpg' }),
        makeTrack({ id: 2, artwork_url: '/art/2.jpg' }),
        makeTrack({ id: 3, artwork_url: '/art/3.jpg' }),
      ],
      total: 3,
      has_more: false,
    }));

    const { result } = renderHook(() =>
      useLibraryData({ view: 'all', autoLoad: true }),
    );

    await waitFor(() => expect(result.current.tracks).toHaveLength(3));

    expect(result.current.tracks[0].albumArt).toBe('/art/1.jpg');
    expect(result.current.tracks[1].albumArt).toBe('/art/2.jpg');
    expect(result.current.tracks[2].albumArt).toBe('/art/3.jpg');
  });

  // --------------------------------------------------------------------------
  // loadMore (pagination)
  // --------------------------------------------------------------------------

  it('maps artwork_url to albumArt in loadMore response', async () => {
    stubFetchSequence([
      // First page — has_more: true enables loadMore
      fakeJsonResponse({
        tracks: [makeTrack({ id: 1, artwork_url: '/art/p1.jpg' })],
        total: 2,
        has_more: true,
      }),
      // Second page
      fakeJsonResponse({
        tracks: [makeTrack({ id: 2, artwork_url: '/art/p2.jpg' })],
        total: 2,
        has_more: false,
      }),
    ]);

    const { result } = renderHook(() =>
      useLibraryData({ view: 'all', autoLoad: true }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.hasMore).toBe(true);

    await act(async () => {
      await result.current.loadMore();
    });

    await waitFor(() => expect(result.current.isLoadingMore).toBe(false));

    expect(result.current.tracks).toHaveLength(2);
    expect(result.current.tracks[0].albumArt).toBe('/art/p1.jpg');
    expect(result.current.tracks[1].albumArt).toBe('/art/p2.jpg');
  });

  it('legacy album_art fallback works in loadMore too', async () => {
    stubFetchSequence([
      fakeJsonResponse({
        tracks: [makeTrack({ id: 1 })],
        total: 2,
        has_more: true,
      }),
      fakeJsonResponse({
        tracks: [makeTrack({ id: 2, album_art: '/art/fallback.jpg' })],
        total: 2,
        has_more: false,
      }),
    ]);

    const { result } = renderHook(() =>
      useLibraryData({ view: 'all', autoLoad: true }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.loadMore();
    });

    await waitFor(() => expect(result.current.isLoadingMore).toBe(false));

    expect(result.current.tracks[1].albumArt).toBe('/art/fallback.jpg');
  });
});
