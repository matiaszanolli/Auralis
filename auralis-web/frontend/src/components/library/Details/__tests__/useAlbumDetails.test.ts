/**
 * useAlbumDetails — snake_case → camelCase mapping (#4568, #4571)
 *
 * `GET /api/albums/{id}/tracks` serialises per-track fields in snake_case
 * (serialize_tracks → Track.to_dict()). The hook used to map them inline with
 * camelCase reads (`t.artworkUrl`, `t.trackNumber`, `t.discNumber`, `t.albumId`)
 * and a `(t: DetailTrack)` annotation that asserted the wrong shape onto raw
 * JSON — so TypeScript endorsed the mistake and every value came back
 * null/blank. The artist column was empty (the wire key is `artists: string[]`)
 * and rows had no track numbers.
 *
 * The album-*level* keys on this endpoint genuinely are snake_case and are read
 * correctly; the regression test below pins that so a future "normalisation"
 * does not break them.
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useAlbumDetails } from '../useAlbumDetails';
import { ApiErrorHandler } from '@/types/api';

const ALBUM_TRACKS_RESPONSE = {
  album_id: 1,
  album_title: 'Reign in Blood',
  artist: 'Slayer',
  year: 1986,
  artwork_url: '/api/albums/1/artwork',
  total_tracks: 2,
  tracks: [
    {
      id: 10,
      title: 'Angel of Death',
      artists: ['Slayer'],
      album: 'Reign in Blood',
      duration: 286,
      genres: ['Thrash Metal'],
      artwork_url: '/api/albums/1/artwork',
      album_id: 1,
      track_number: 3,
      disc_number: 2,
      favorite: true,
      year: 1986,
    },
    {
      id: 11,
      title: 'Raining Blood',
      artists: ['Slayer'],
      album: 'Reign in Blood',
      duration: 250,
      album_id: 1,
      track_number: 1,
      disc_number: 1,
    },
  ],
};

describe('useAlbumDetails', () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ALBUM_TRACKS_RESPONSE,
    }) as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const load = async () => {
    const { result } = renderHook(() => useAlbumDetails(1));
    await waitFor(() => expect(result.current.loading).toBe(false));
    return result;
  };

  // #5118: the backend exposes favorites as POST (set true) / DELETE (set
  // false), with no toggle semantic. The hook used to always POST and then
  // negate a local boolean that started `false` unconditionally — so the heart
  // misreported stored state on load, and un-favoriting never reached the
  // server while the UI reported success.
  describe('favorite state (#5118)', () => {
    /** Route the album fetch to the fixture and the favorite call to `body`. */
    const mockFetch = (body: unknown = { favorite: false }) => {
      const fetchMock = vi.fn().mockImplementation((url: string) => {
        if (String(url).includes('/favorite')) {
          return Promise.resolve({ ok: true, json: async () => body });
        }
        return Promise.resolve({ ok: true, json: async () => ALBUM_TRACKS_RESPONSE });
      });
      global.fetch = fetchMock as unknown as typeof fetch;
      return fetchMock;
    };

    it('seeds isFavorite from the first track rather than defaulting to false', async () => {
      mockFetch();
      const result = await load();

      // Fixture track 10 has favorite: true.
      expect(result.current.isFavorite).toBe(true);
    });

    it('issues DELETE when the album is already favorited', async () => {
      const fetchMock = mockFetch({ favorite: false });
      const result = await load();
      expect(result.current.isFavorite).toBe(true);

      await act(async () => {
        await result.current.toggleFavorite();
      });

      const favoriteCall = fetchMock.mock.calls.find(([url]) =>
        String(url).includes('/favorite')
      );
      expect(favoriteCall?.[0]).toBe('/api/library/tracks/10/favorite');
      expect(favoriteCall?.[1]).toMatchObject({ method: 'DELETE' });
      expect(result.current.isFavorite).toBe(false);
    });

    it('issues POST when the album is not favorited', async () => {
      const fetchMock = vi.fn().mockImplementation((url: string) => {
        if (String(url).includes('/favorite')) {
          return Promise.resolve({ ok: true, json: async () => ({ favorite: true }) });
        }
        return Promise.resolve({
          ok: true,
          // Same fixture, but the first track is not favorited.
          json: async () => ({
            ...ALBUM_TRACKS_RESPONSE,
            tracks: [{ ...ALBUM_TRACKS_RESPONSE.tracks[0], favorite: false }],
          }),
        });
      });
      global.fetch = fetchMock as unknown as typeof fetch;

      const result = await load();
      expect(result.current.isFavorite).toBe(false);

      await act(async () => {
        await result.current.toggleFavorite();
      });

      const favoriteCall = fetchMock.mock.calls.find(([url]) =>
        String(url).includes('/favorite')
      );
      expect(favoriteCall?.[1]).toMatchObject({ method: 'POST' });
      expect(result.current.isFavorite).toBe(true);
    });

    it('takes the resulting state from the response, not from negating locally', async () => {
      // Server reports the track is still favorited (e.g. a concurrent change).
      // The old code blindly flipped to false; the new code must trust the server.
      mockFetch({ favorite: true });
      const result = await load();
      expect(result.current.isFavorite).toBe(true);

      await act(async () => {
        await result.current.toggleFavorite();
      });

      expect(result.current.isFavorite).toBe(true);
    });

    it('falls back to a local flip when the response carries no favorite field', async () => {
      mockFetch({});
      const result = await load();

      await act(async () => {
        await result.current.toggleFavorite();
      });

      expect(result.current.isFavorite).toBe(false);
    });
  });

  it('maps per-track snake_case fields to the camelCase domain shape', async () => {
    const result = await load();

    const track = result.current.album!.tracks![0];
    expect(track.trackNumber).toBe(3);
    expect(track.discNumber).toBe(2);
    expect(track.albumId).toBe(1);
    expect(track.artworkUrl).toBe('/api/albums/1/artwork');
    expect(track.favorite).toBe(true);
  });

  it('resolves artist from the artists[] array, not a non-existent `artist` key', async () => {
    const result = await load();

    expect(result.current.album!.tracks![0].artist).toBe('Slayer');
    expect(result.current.album!.tracks![0].genre).toBe('Thrash Metal');
  });

  it('keeps the album-level snake_case reads working', async () => {
    const result = await load();

    const album = result.current.album!;
    expect(album.id).toBe(1);
    expect(album.title).toBe('Reign in Blood');
    expect(album.artist).toBe('Slayer');
    expect(album.track_count).toBe(2);
    expect(album.year).toBe(1986);
  });

  it('sums total_duration across the transformed tracks', async () => {
    const result = await load();

    expect(result.current.album!.total_duration).toBe(536);
  });

  it('preserves the backend-supplied track order (server-side disc/track sort)', async () => {
    const result = await load();

    expect(result.current.album!.tracks!.map((t) => t.id)).toEqual([10, 11]);
  });

  it('tolerates a response with no tracks key', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ album_id: 2, album_title: 'Empty', total_tracks: 0 }),
    }) as unknown as typeof fetch;

    const result = await load();

    expect(result.current.album!.tracks).toEqual([]);
    expect(result.current.album!.total_duration).toBe(0);
    expect(result.current.error).toBeNull();
  });

  // #4643: routed through get()/ApiErrorHandler so the real HTTP status
  // survives instead of collapsing every non-OK response into an identical,
  // status-less Error.
  describe('error status (#4643)', () => {
    const mockFailedFetch = (status: number, detail: string) => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status,
        statusText: 'Error',
        json: async () => ({ detail }),
      }) as unknown as typeof fetch;
    };

    it('surfaces a 404 as an identifiable not-found error', async () => {
      mockFailedFetch(404, 'Album 999 not found');

      const result = await load();

      expect(result.current.album).toBeNull();
      expect(result.current.error).not.toBeNull();
      expect(ApiErrorHandler.isNotFound(result.current.error!)).toBe(true);
      expect(result.current.error!.message).toBe('Album 999 not found');
    });

    it('surfaces a 500 as a distinguishable server error, not a not-found', async () => {
      mockFailedFetch(500, 'Internal server error');

      const result = await load();

      expect(result.current.album).toBeNull();
      expect(result.current.error).not.toBeNull();
      expect(ApiErrorHandler.isNotFound(result.current.error!)).toBe(false);
      expect(ApiErrorHandler.isNetworkError(result.current.error!)).toBe(true);
    });

    it('produces no error state when the request is aborted mid-flight', async () => {
      // The internal AbortController fires on unmount; simulate that by
      // having fetch reject with the DOMException shape a real abort throws.
      global.fetch = vi.fn().mockImplementation(
        (_url: string, init?: { signal?: AbortSignal }) =>
          new Promise((_resolve, reject) => {
            init?.signal?.addEventListener('abort', () =>
              reject(new DOMException('The operation was aborted.', 'AbortError'))
            );
          })
      ) as unknown as typeof fetch;

      const { result, unmount } = renderHook(() => useAlbumDetails(1));
      unmount(); // triggers the effect cleanup's controller.abort()

      // Give the rejected promise a tick to settle before asserting.
      await act(async () => {
        await Promise.resolve();
      });

      expect(result.current.error).toBeNull();
    });
  });
});
