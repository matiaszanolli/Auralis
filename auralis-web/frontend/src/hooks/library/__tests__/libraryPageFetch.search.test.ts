/**
 * Backend-driven library search (#5866)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 * The top-bar search only ever filtered the already-loaded pages
 * (first 50 rows + scrolled pages), so in a large library any match outside
 * them showed as a false "no results" — while the backend's `search=`
 * (title/artist/album ILIKE with correct `total`) had no mounted caller.
 * The paginated tracks fetch now carries the debounced query; albums and
 * artists views forward it to their query hooks.
 */

import { describe, expect, it } from 'vitest';
import { tracksEndpoint, PAGE_LIMIT } from '../libraryPageFetch';

describe('tracksEndpoint carries the server-side search (#5866)', () => {
  it('appends search when present', () => {
    const url = new URL(tracksEndpoint('songs', 100, 'radiohead'), 'http://x');
    expect(url.pathname).toBe('/api/library/tracks');
    expect(url.searchParams.get('search')).toBe('radiohead');
    expect(url.searchParams.get('limit')).toBe(String(PAGE_LIMIT));
    expect(url.searchParams.get('offset')).toBe('100');
  });

  it('omits the param for an empty or whitespace query', () => {
    expect(tracksEndpoint('songs', 0, '')).not.toContain('search=');
    expect(tracksEndpoint('songs', 0, '   ')).not.toContain('search=');
  });

  it('keeps the favourites endpoint routing with search', () => {
    const url = new URL(tracksEndpoint('favourites', 0, 'beatles'), 'http://x');
    expect(url.pathname).toBe('/api/library/tracks/favorites');
    expect(url.searchParams.get('search')).toBe('beatles');
  });
});
