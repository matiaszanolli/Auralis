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

import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useAlbumDetails } from '../useAlbumDetails';

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

  it('surfaces a failed request as an error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false }) as unknown as typeof fetch;

    const result = await load();

    expect(result.current.error).toBe('Failed to fetch album details');
    expect(result.current.album).toBeNull();
  });
});
