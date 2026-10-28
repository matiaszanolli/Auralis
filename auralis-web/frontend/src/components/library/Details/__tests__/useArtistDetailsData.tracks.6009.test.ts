/**
 * The artist detail view gets the artist's tracks (#6009)
 *
 * useArtistDetailsData built the artist with a hard-coded `tracks: []`; the
 * detail response carries albums only, so "All Tracks" was empty and Play All /
 * Shuffle did nothing. ArtistDetailView's own spec mocks this hook, which is how
 * it stayed hidden.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useArtistDetailsData } from '../useArtistDetailsData';

const mockGet = vi.fn();
vi.mock('@/utils/apiRequest', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/utils/apiRequest')>()),
  get: (...args: unknown[]) => mockGet(...args),
}));

const detail = {
  id: 7,
  name: 'Queen',
  album_count: 1,
  track_count: 2,
  albums: [{ id: 10, title: 'A Night at the Opera', year: 1975, track_count: 2, total_duration: 600 }],
};

const tracksResponse = {
  id: 7,
  name: 'Queen',
  total_tracks: 2,
  tracks: [
    { id: 100, title: 'Bohemian Rhapsody', album: 'A Night at the Opera', album_id: 10, duration: 354, track_number: 11 },
    { id: 101, title: 'Orphan', album: null, album_id: null, duration: 120 },
  ],
};

describe('useArtistDetailsData tracks (#6009)', () => {
  beforeEach(() => {
    mockGet.mockReset();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  it('loads the artist\'s tracks from the tracks endpoint as playable DetailTracks', async () => {
    mockGet.mockImplementation(async (url: string) => (url.endsWith('/tracks') ? tracksResponse : detail));

    const { result } = renderHook(() => useArtistDetailsData(7));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.artist?.tracks).toEqual([
      expect.objectContaining({ id: 100, title: 'Bohemian Rhapsody', artist: 'Queen', album: 'A Night at the Opera', albumId: 10, trackNumber: 11 }),
      expect.objectContaining({ id: 101, title: 'Orphan', artist: 'Queen', album: '', albumId: null }),
    ]);
    expect(result.current.artist?.albums).toHaveLength(1);
  });

  it('still shows the artist and albums when only the track list fails', async () => {
    mockGet.mockImplementation(async (url: string) => {
      if (url.endsWith('/tracks')) throw new Error('boom');
      return detail;
    });

    const { result } = renderHook(() => useArtistDetailsData(7));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBeNull();
    expect(result.current.artist?.name).toBe('Queen');
    expect(result.current.artist?.tracks).toEqual([]);
  });
});
