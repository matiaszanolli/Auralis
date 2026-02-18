/**
 * Tests for Artwork Service
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tests the artwork management service (extract, download, delete, URL generation)
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';

// Setup fetch mock with proper Vitest types
const createFetchMock = () => vi.fn();
let fetchMock = createFetchMock();
vi.stubGlobal('fetch', fetchMock);

// Helper function to access the mocked fetch with proper types
const mockFetch = () => fetchMock as any;
import {
  extractArtwork,
  downloadArtwork,
  deleteArtwork,
  getArtworkUrl,
  type ArtworkResponse,
} from '../artworkService';

// Mock fetch
global.fetch = vi.fn();

describe.skip('ArtworkService', () => {
  // SKIPPED: Tests need migration to MSW - currently mock fetch directly which conflicts with MSW
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('extractArtwork', () => {
    it('should extract artwork successfully', async () => {
      const mockResponse: ArtworkResponse = {
        message: 'Artwork extracted successfully',
        artwork_path: '/path/to/artwork.jpg',
        album_id: 1,
        artist: 'Test Artist',
        album: 'Test Album',
      };

      mockFetch().mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await extractArtwork(1);

      expect(mockFetch()).toHaveBeenCalledWith(
        '/api/albums/1/artwork/extract',
        { method: 'POST' }
      );
      expect(result).toEqual(mockResponse);
    });

    it('should throw error on failed extraction', async () => {
      mockFetch().mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: 'No artwork found in audio files' }),
      });

      await expect(extractArtwork(1)).rejects.toThrow('No artwork found in audio files');
    });

    it('should throw generic error when no detail provided', async () => {
      mockFetch().mockResolvedValueOnce({
        ok: false,
        json: async () => ({}),
      });

      await expect(extractArtwork(1)).rejects.toThrow('Failed to extract artwork');
    });

    it('should handle network errors', async () => {
      mockFetch().mockRejectedValueOnce(new Error('Network error'));

      await expect(extractArtwork(1)).rejects.toThrow('Network error');
    });

    it('should extract artwork for different album IDs', async () => {
      const mockResponse: ArtworkResponse = {
        message: 'Success',
        artwork_path: '/artwork.jpg',
        album_id: 999,
      };

      mockFetch().mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      await extractArtwork(999);

      expect(mockFetch()).toHaveBeenCalledWith(
        '/api/albums/999/artwork/extract',
        { method: 'POST' }
      );
    });
  });

  describe('downloadArtwork', () => {
    it('should download artwork successfully', async () => {
      const mockResponse: ArtworkResponse = {
        message: 'Artwork downloaded from MusicBrainz',
        artwork_path: '/path/to/downloaded.jpg',
        album_id: 1,
        artist: 'Test Artist',
        album: 'Test Album',
      };

      mockFetch().mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await downloadArtwork(1);

      expect(mockFetch()).toHaveBeenCalledWith(
        '/api/albums/1/artwork/download',
        { method: 'POST' }
      );
      expect(result).toEqual(mockResponse);
    });

    it('should throw error on failed download', async () => {
      mockFetch().mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: 'Album not found online' }),
      });

      await expect(downloadArtwork(1)).rejects.toThrow('Album not found online');
    });

    it('should throw generic error when no detail provided', async () => {
      mockFetch().mockResolvedValueOnce({
        ok: false,
        json: async () => ({}),
      });

      await expect(downloadArtwork(1)).rejects.toThrow('Failed to download artwork');
    });

    it('should handle API timeout', async () => {
      mockFetch().mockRejectedValueOnce(new Error('Request timeout'));

      await expect(downloadArtwork(1)).rejects.toThrow('Request timeout');
    });

    it('should download for various album IDs', async () => {
      for (const albumId of [1, 42, 9999]) {
        mockFetch().mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            message: 'Downloaded',
            artwork_path: '/artwork.jpg',
            album_id: albumId,
          }),
        });

        await downloadArtwork(albumId);

        expect(mockFetch()).toHaveBeenCalledWith(
          `/api/albums/${albumId}/artwork/download`,
          { method: 'POST' }
        );
      }
    });
  });

  describe('deleteArtwork', () => {
    it('should delete artwork successfully', async () => {
      const mockResponse = {
        message: 'Artwork deleted successfully',
        album_id: 1,
      };

      mockFetch().mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await deleteArtwork(1);

      expect(mockFetch()).toHaveBeenCalledWith(
        '/api/albums/1/artwork',
        { method: 'DELETE' }
      );
      expect(result).toEqual(mockResponse);
    });

    it('should throw error on failed deletion', async () => {
      mockFetch().mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: 'Artwork not found' }),
      });

      await expect(deleteArtwork(1)).rejects.toThrow('Artwork not found');
    });

    it('should throw generic error when no detail provided', async () => {
      mockFetch().mockResolvedValueOnce({
        ok: false,
        json: async () => ({}),
      });

      await expect(deleteArtwork(1)).rejects.toThrow('Failed to delete artwork');
    });

    it('should handle permission errors', async () => {
      mockFetch().mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: 'Permission denied' }),
      });

      await expect(deleteArtwork(1)).rejects.toThrow('Permission denied');
    });

    it('should delete for different album IDs', async () => {
      for (const albumId of [1, 100, 5000]) {
        mockFetch().mockResolvedValueOnce({
          ok: true,
          json: async () => ({ message: 'Deleted', album_id: albumId }),
        });

        await deleteArtwork(albumId);

        expect(mockFetch()).toHaveBeenCalledWith(
          `/api/albums/${albumId}/artwork`,
          { method: 'DELETE' }
        );
      }
    });
  });

  describe('getArtworkUrl', () => {
    it('should generate a stable artwork URL without a timestamp', () => {
      const url = getArtworkUrl(1);

      expect(url).toMatch(/^http:\/\/localhost:8765\/api\/albums\/1\/artwork$/);
      expect(url).not.toContain('?t=');
    });

    it('should return the same URL for consecutive calls (cache-friendly)', () => {
      const url1 = getArtworkUrl(1);
      const url2 = getArtworkUrl(1);

      expect(url1).toBe(url2);
    });

    it('should generate URLs for different album IDs', () => {
      const url1 = getArtworkUrl(1);
      const url42 = getArtworkUrl(42);
      const url999 = getArtworkUrl(999);

      expect(url1).toContain('/albums/1/artwork');
      expect(url42).toContain('/albums/42/artwork');
      expect(url999).toContain('/albums/999/artwork');
    });

    it('should handle album ID 0', () => {
      const url = getArtworkUrl(0);

      expect(url).toContain('/albums/0/artwork');
    });

    it('should handle large album IDs', () => {
      const url = getArtworkUrl(999999999);

      expect(url).toContain('/albums/999999999/artwork');
    });

    it('should return string type', () => {
      const url = getArtworkUrl(1);

      expect(typeof url).toBe('string');
    });
  });

  describe('Integration scenarios', () => {
    it('should handle extract -> download fallback workflow', async () => {
      // First, extraction fails
      mockFetch().mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: 'No embedded artwork' }),
      });

      await expect(extractArtwork(1)).rejects.toThrow('No embedded artwork');

      // Then, download succeeds
      mockFetch().mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          message: 'Downloaded from MusicBrainz',
          artwork_path: '/artwork.jpg',
          album_id: 1,
        }),
      });

      const result = await downloadArtwork(1);
      expect(result.message).toContain('Downloaded');
    });

    it('should handle extract -> delete -> extract workflow', async () => {
      // Extract artwork
      mockFetch().mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          message: 'Extracted',
          artwork_path: '/old.jpg',
          album_id: 1,
        }),
      });

      await extractArtwork(1);

      // Delete artwork
      mockFetch().mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: 'Deleted', album_id: 1 }),
      });

      await deleteArtwork(1);

      // Extract again
      mockFetch().mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          message: 'Re-extracted',
          artwork_path: '/new.jpg',
          album_id: 1,
        }),
      });

      const result = await extractArtwork(1);
      expect(result.message).toBe('Re-extracted');
    });

    it('should handle multiple concurrent operations', async () => {
      const promises = [1, 2, 3].map(id => {
        mockFetch().mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            message: 'Success',
            artwork_path: `/artwork${id}.jpg`,
            album_id: id,
          }),
        });
        return extractArtwork(id);
      });

      const results = await Promise.all(promises);

      expect(results).toHaveLength(3);
      expect(results[0].album_id).toBe(1);
      expect(results[1].album_id).toBe(2);
      expect(results[2].album_id).toBe(3);
    });
  });

  describe('Error handling edge cases', () => {
    it('should handle malformed JSON response', async () => {
      mockFetch().mockResolvedValueOnce({
        ok: false,
        json: async () => { throw new Error('Invalid JSON'); },
      });

      await expect(extractArtwork(1)).rejects.toThrow();
    });

    it('should handle null response', async () => {
      mockFetch().mockResolvedValueOnce({
        ok: true,
        json: async () => null,
      });

      const result = await extractArtwork(1);
      expect(result).toBeNull();
    });

    it('should handle 404 errors', async () => {
      mockFetch().mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({ detail: 'Album not found' }),
      });

      await expect(downloadArtwork(999999)).rejects.toThrow('Album not found');
    });

    it('should handle 500 errors', async () => {
      mockFetch().mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ detail: 'Internal server error' }),
      });

      await expect(extractArtwork(1)).rejects.toThrow('Internal server error');
    });

    it('should handle timeout errors', async () => {
      mockFetch().mockImplementationOnce(() =>
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error('Timeout')), 100)
        )
      );

      await expect(downloadArtwork(1)).rejects.toThrow('Timeout');
    });
  });
});

// ============================================================================
// getArtworkUrl — non-skipped tests (pure function, no MSW needed)
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
    // Simulate rapid re-renders: 10 calls in a tight loop must all return identical strings
    const albumId = 5;
    const urls = Array.from({ length: 10 }, () => getArtworkUrl(albumId));
    const unique = new Set(urls);
    expect(unique.size).toBe(1);
  });

  it('handles edge-case albumIds (0, large numbers)', () => {
    expect(getArtworkUrl(0)).toContain('/albums/0/artwork');
    expect(getArtworkUrl(999999999)).toContain('/albums/999999999/artwork');
  });
});
