/**
 * Tests for Artwork Service
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Covers the two URL builders, which are pure functions — no HTTP, so no
 * apiRequest mock and nothing for MSW to intercept.
 *
 * #5214 removed the extract/download/delete suites along with the functions
 * they exercised; those had tests but no caller anywhere in the app.
 */

import { describe, it, expect } from 'vitest';

import { getArtworkUrl, withArtworkSize } from '../artworkService';

// ============================================================================
// getArtworkUrl — pure function, no HTTP calls, no MSW needed
// ============================================================================

describe('getArtworkUrl — stable URL (issue #2387)', () => {
  it('returns a stable URL without a timestamp query parameter', () => {
    const url = getArtworkUrl(1);
    expect(url).not.toContain('?t=');
    expect(url).not.toContain('?');
    expect(url).toMatch(/\/api\/albums\/1\/artwork$/);
  });

  it('returns the same URL on consecutive calls for the same albumId', () => {
    const url1 = getArtworkUrl(1);
    const url2 = getArtworkUrl(1);
    expect(url1).toBe(url2);
  });

  it('returns different URLs for different albumIds', () => {
    expect(getArtworkUrl(1)).not.toBe(getArtworkUrl(2));
    expect(getArtworkUrl(1)).toContain('/albums/1/artwork');
    expect(getArtworkUrl(42)).toContain('/albums/42/artwork');
  });

  it('URL is browser-cacheable: same string every millisecond', () => {
    const albumId = 5;
    const urls = Array.from({ length: 10 }, () => getArtworkUrl(albumId));
    expect(new Set(urls).size).toBe(1);
  });

  it('handles edge-case albumIds (0, large numbers)', () => {
    expect(getArtworkUrl(0)).toContain('/albums/0/artwork');
    expect(getArtworkUrl(999999999)).toContain('/albums/999999999/artwork');
  });
});

// ============================================================================
// getArtworkUrl size/revision + withArtworkSize (#4447)
// ============================================================================

describe('getArtworkUrl — size / revision (#4447)', () => {
  it('appends a rounded size param when a size hint is given', () => {
    expect(getArtworkUrl(1, { size: 80 })).toBe('/api/albums/1/artwork?size=80');
    expect(getArtworkUrl(1, { size: 63.6 })).toBe('/api/albums/1/artwork?size=64');
  });

  it('omits size for zero/negative/undefined hints', () => {
    expect(getArtworkUrl(1, { size: 0 })).toBe('/api/albums/1/artwork');
    expect(getArtworkUrl(1, { size: -10 })).toBe('/api/albums/1/artwork');
    expect(getArtworkUrl(1)).toBe('/api/albums/1/artwork');
  });

  it('combines size and revision', () => {
    expect(getArtworkUrl(7, { size: 256, revision: 3 })).toBe(
      '/api/albums/7/artwork?size=256&v=3'
    );
  });

  it('appends only the revision when no size is given (unchanged behavior)', () => {
    expect(getArtworkUrl(7, { revision: 2 })).toBe('/api/albums/7/artwork?v=2');
  });
});

describe('withArtworkSize (#4447)', () => {
  it('appends a size param to an artwork endpoint URL', () => {
    expect(withArtworkSize('/api/albums/9/artwork', 80)).toBe(
      '/api/albums/9/artwork?size=80'
    );
    expect(withArtworkSize('/api/albums/9/artwork?v=4', 80)).toBe(
      '/api/albums/9/artwork?v=4&size=80'
    );
  });

  it('leaves non-artwork, already-sized, and empty URLs untouched', () => {
    expect(withArtworkSize('data:image/png;base64,AAAA', 80)).toBe(
      'data:image/png;base64,AAAA'
    );
    expect(withArtworkSize('/api/albums/9/artwork?size=128', 80)).toBe(
      '/api/albums/9/artwork?size=128'
    );
    expect(withArtworkSize(undefined, 80)).toBeUndefined();
    expect(withArtworkSize('/api/albums/9/artwork', 0)).toBe('/api/albums/9/artwork');
  });

  // #4526: artist artwork is an ABSOLUTE external CDN URL — the one artwork
  // field deliberately not rewritten to an /api path. The old guard was a bare
  // `url.includes('/artwork')`, so any external URL happening to contain that
  // substring got `?size=N` appended and sent to a third-party host that has no
  // idea what it means. Same-origin is now the actual condition.
  it('never appends a size to an absolute external URL', () => {
    const external = [
      'https://lastfm.freetls.fastly.net/i/u/770x0/abc.jpg',
      'https://i.discogs.com/artwork/xyz.jpeg',
      'https://upload.wikimedia.org/wikipedia/commons/artwork/pic.png',
      'https://example.com/api/albums/9/artwork',
      'http://localhost:8765/api/albums/9/artwork',
      '//cdn.example.com/artwork/pic.jpg',
    ];
    for (const url of external) {
      expect(withArtworkSize(url, 256)).toBe(url);
    }
  });

  it('still appends to same-origin artwork paths', () => {
    expect(withArtworkSize('/api/artists/3/artwork', 256)).toBe(
      '/api/artists/3/artwork?size=256'
    );
  });
});
