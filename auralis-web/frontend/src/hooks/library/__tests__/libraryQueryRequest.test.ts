/**
 * libraryQueryRequest — pure request/response shaping for useLibraryQuery (#5043)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * These ran only inside the hook body, so their tests had to mount the hook
 * and ended up exercising the mock. Called directly here, with the real
 * transformers, so a wrong endpoint or a dropped snake→camel field fails on
 * the logic itself.
 */

import { describe, it, expect } from 'vitest';
import {
  QUERY_TYPE_ENDPOINT,
  buildEndpoint,
  extractItemsFromResponse,
} from '@/hooks/library/libraryQueryRequest';
import type { Album, Artist, Track } from '@/types/domain';

describe('buildEndpoint', () => {
  it('uses each query type’s canonical router, not /api/library/* for all (#2379)', () => {
    expect(QUERY_TYPE_ENDPOINT).toEqual({
      tracks: '/api/library/tracks',
      albums: '/api/albums',
      artists: '/api/artists',
    });
  });

  it('defaults to a first page of 50', () => {
    expect(buildEndpoint('tracks', {})).toBe('/api/library/tracks?limit=50&offset=0');
  });

  it('carries limit, offset, search and order_by', () => {
    expect(buildEndpoint('albums', { limit: 20, search: 'abba', orderBy: 'title' }, 40)).toBe(
      '/api/albums?limit=20&offset=40&search=abba&order_by=title'
    );
  });

  it('URL-encodes the search term', () => {
    expect(buildEndpoint('artists', { search: 'sigur rós & co' })).toBe(
      '/api/artists?limit=50&offset=0&search=sigur+r%C3%B3s+%26+co'
    );
  });

  it('omits empty search and ordering', () => {
    expect(buildEndpoint('tracks', { search: '', orderBy: '' }, 100)).toBe(
      '/api/library/tracks?limit=50&offset=100'
    );
  });

  it('returns a custom endpoint verbatim, ignoring paging options', () => {
    expect(buildEndpoint('tracks', { endpoint: '/api/custom?x=1', limit: 5 }, 10)).toBe(
      '/api/custom?x=1'
    );
  });
});

describe('extractItemsFromResponse', () => {
  it('reads tracks from the type-specific field and maps snake_case to camelCase', () => {
    const [track] = extractItemsFromResponse<Track>(
      { tracks: [{ id: 1, title: 'Song', artwork_url: '/art/1.jpg', album_id: 7 }] },
      'tracks'
    );

    expect(track).toMatchObject({ id: 1, title: 'Song', artworkUrl: '/art/1.jpg', albumId: 7 });
  });

  it('reads albums through the canonical album transformer', () => {
    const [album] = extractItemsFromResponse<Album>(
      { albums: [{ id: 2, title: 'Record', artist_id: 3, artwork_url: null, track_count: 9 }] },
      'albums'
    );

    expect(album).toMatchObject({ id: 2, artistId: 3, trackCount: 9, totalDuration: 0 });
    expect(album.artworkUrl).toBeUndefined();
  });

  it('reads artists through the canonical artist transformer', () => {
    const [artist] = extractItemsFromResponse<Artist>(
      { artists: [{ id: 4, name: 'Band', track_count: 12, album_count: 2, created_at: '2024-01-01' }] },
      'artists'
    );

    expect(artist).toMatchObject({ id: 4, name: 'Band', trackCount: 12, albumCount: 2, dateAdded: '2024-01-01' });
  });

  it('falls back to a generic `items` field', () => {
    const items = extractItemsFromResponse<Artist>({ items: [{ id: 5, name: 'Solo' }] }, 'artists');

    expect(items).toHaveLength(1);
    expect(items[0].name).toBe('Solo');
  });

  it('takes only the field for the requested type', () => {
    const response = { tracks: [{ id: 1, title: 'Song' }], albums: [{ id: 2, title: 'Record' }] };

    expect(extractItemsFromResponse<Album>(response, 'albums').map((a) => a.id)).toEqual([2]);
  });

  it('returns an empty list when the response carries no items', () => {
    expect(extractItemsFromResponse<Track>({}, 'tracks')).toEqual([]);
  });

  it('throws on a query type it does not know, rather than guessing a field', () => {
    expect(() => extractItemsFromResponse({}, 'playlists' as never)).toThrow(
      'Unhandled LibraryQueryType: playlists'
    );
  });
});
