/**
 * Library API Integration Tests — SKIPPED (#5119)
 *
 * These tests exercise no component at all — bare `fetch()` against MSW, defined entirely within this file. No
 * production module is imported: the only non-test-infrastructure imports are
 * vitest, @testing-library, msw and react. The suite could therefore only ever
 * validate its own fixture, never regress with production code — deleting the
 * feature it names would leave every test in this file green.
 *
 * That is the same false-green defect #3935 fixed in
 * `src/tests/integration/streaming-audio/streaming-mse.test.tsx`, which was
 * skipped rather than deleted for the same reason. The fix was applied to that
 * one file and never swept across this directory (#5119).
 *
 * Real coverage for this area lives in `src/services/__tests__/libraryService` and the library hook specs.
 *
 * Kept (skipped, not deleted) as a starting point should these be rewritten to
 * render the production component/hook they claim to cover — see
 * `library-management.test.tsx` and `playlist-management.test.tsx` in this
 * directory for the pattern that does it correctly.
 */

import { describe, it, expect } from 'vitest';

// API base URL
const API_BASE = 'http://localhost:8765/api';

describe.skip('Library API Integration Tests', () => {
  describe('Track Endpoints', () => {
    it('should fetch tracks with pagination', async () => {
      const response = await fetch(`${API_BASE}/library/tracks?limit=10&offset=0`);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('tracks');
      expect(data).toHaveProperty('total');
      expect(data).toHaveProperty('has_more');
      expect(data.tracks).toHaveLength(10);
      expect(data.total).toBe(100);
      expect(data.has_more).toBe(true);
    });

    it('should fetch second page of tracks', async () => {
      const response = await fetch(`${API_BASE}/library/tracks?limit=10&offset=10`);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.tracks).toHaveLength(10);
      expect(data.tracks[0].id).toBe(11); // Verify offset worked
    });

    it('should search tracks by title', async () => {
      const response = await fetch(`${API_BASE}/library/tracks?search=Track%201`);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.tracks.length).toBeGreaterThan(0);
      expect(data.tracks.every((t: any) => t.title.includes('Track 1'))).toBe(true);
    });

    it('should fetch single track by ID', async () => {
      const response = await fetch(`${API_BASE}/library/tracks/1`);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.id).toBe(1);
      expect(data.title).toBe('Test Track 1');
    });

    it('should return 404 for non-existent track', async () => {
      const response = await fetch(`${API_BASE}/library/tracks/9999`);
      const data = await response.json();

      expect(response.status).toBe(404);
      expect(data).toHaveProperty('error');
    });

    it('should toggle track favorite', async () => {
      const response = await fetch(`${API_BASE}/library/tracks/1/favorite`, {
        method: 'POST',
      });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data).toHaveProperty('favorite');
    });

    it('should update track metadata', async () => {
      const updates = {
        title: 'Updated Title',
        artist: 'Updated Artist',
      };

      const response = await fetch(`${API_BASE}/library/tracks/1`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.track_id).toBe(1);
      expect(data.updated).toEqual(updates);
    });
  });

  describe('Album Endpoints', () => {
    it('should fetch all albums', async () => {
      const response = await fetch(`${API_BASE}/library/albums`);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('albums');
      expect(data.albums).toHaveLength(20);
    });

    it('should fetch album by ID', async () => {
      const response = await fetch(`${API_BASE}/library/albums/1`);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.id).toBe(1);
      expect(data.title).toBe('Album 1');
    });

    it('should fetch album tracks', async () => {
      const response = await fetch(`${API_BASE}/library/albums/1/tracks`);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('tracks');
      expect(Array.isArray(data.tracks)).toBe(true);
    });

    it('should return 404 for non-existent album', async () => {
      const response = await fetch(`${API_BASE}/library/albums/9999`);
      const data = await response.json();

      expect(response.status).toBe(404);
      expect(data).toHaveProperty('error');
    });
  });

  describe('Artist Endpoints', () => {
    it('should fetch all artists', async () => {
      const response = await fetch(`${API_BASE}/library/artists`);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('artists');
      expect(data.artists).toHaveLength(10);
    });

    it('should fetch artist by ID', async () => {
      const response = await fetch(`${API_BASE}/library/artists/1`);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.id).toBe(1);
      expect(data.name).toBe('Artist 1');
    });

    it('should fetch artist tracks', async () => {
      const response = await fetch(`${API_BASE}/library/artists/1/tracks`);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('tracks');
      expect(Array.isArray(data.tracks)).toBe(true);
    });

    it('should return 404 for non-existent artist', async () => {
      const response = await fetch(`${API_BASE}/library/artists/9999`);
      const data = await response.json();

      expect(response.status).toBe(404);
      expect(data).toHaveProperty('error');
    });
  });

  describe('Library Scan', () => {
    it('should trigger library scan', async () => {
      const response = await fetch(`${API_BASE}/library/scan`, {
        method: 'POST',
      });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data).toHaveProperty('scanned');
      expect(data).toHaveProperty('added');
    });
  });

  describe('Error Handling', () => {
    it('should handle 404 errors', async () => {
      const response = await fetch(`${API_BASE}/not-found`);
      const data = await response.json();

      expect(response.status).toBe(404);
      expect(data).toHaveProperty('error');
    });

    it('should handle 500 server errors', async () => {
      const response = await fetch(`${API_BASE}/server-error`);
      const data = await response.json();

      expect(response.status).toBe(500);
      expect(data).toHaveProperty('error');
    });
  });

  describe('Response Time', () => {
    it('should respond within acceptable time', async () => {
      const startTime = Date.now();
      await fetch(`${API_BASE}/library/tracks?limit=10&offset=0`);
      const endTime = Date.now();

      const responseTime = endTime - startTime;
      expect(responseTime).toBeLessThan(500); // Should respond within 500ms
    });
  });
});
