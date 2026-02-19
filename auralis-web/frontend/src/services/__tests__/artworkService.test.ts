/**
 * Tests for Artwork Service
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tests the artwork management service (extract, download, delete, URL generation).
 *
 * Mocking strategy: vi.mock on utils/apiRequest so MSW is not disturbed.
 * The old vi.stubGlobal('fetch') pattern was removed — it conflicted with MSW
 * interception (fixes #2366).
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';

vi.mock('../../utils/apiRequest', () => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  APIRequestError: class APIRequestError extends Error {
    constructor(message: string, public statusCode: number, public detail?: string) {
      super(message);
      this.name = 'APIRequestError';
    }
  },
}));

import {
  extractArtwork,
  downloadArtwork,
  deleteArtwork,
  getArtworkUrl,
  type ArtworkResponse,
} from '../artworkService';
import { post, del } from '../../utils/apiRequest';

const mockPost = post as ReturnType<typeof vi.fn>;
const mockDel = del as ReturnType<typeof vi.fn>;

const mockArtworkResponse: ArtworkResponse = {
  message: 'Artwork extracted successfully',
  artwork_path: '/path/to/artwork.jpg',
  album_id: 1,
  artist: 'Test Artist',
  album: 'Test Album',
};

describe('ArtworkService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('extractArtwork', () => {
    it('should extract artwork successfully', async () => {
      mockPost.mockResolvedValueOnce(mockArtworkResponse);

      const result = await extractArtwork(1);

      expect(mockPost).toHaveBeenCalledWith(
        '/api/albums/1/artwork/extract',
        expect.objectContaining({ albumId: 1 })
      );
      expect(result).toEqual(mockArtworkResponse);
    });

    it('should throw error on failed extraction', async () => {
      mockPost.mockRejectedValueOnce(new Error('No artwork found in audio files'));

      await expect(extractArtwork(1)).rejects.toThrow('No artwork found in audio files');
    });

    it('should handle network errors', async () => {
      mockPost.mockRejectedValueOnce(new Error('Network error'));

      await expect(extractArtwork(1)).rejects.toThrow('Network error');
    });

    it('should extract artwork for different album IDs', async () => {
      for (const albumId of [1, 42, 999]) {
        mockPost.mockResolvedValueOnce({ ...mockArtworkResponse, album_id: albumId });

        await extractArtwork(albumId);

        expect(mockPost).toHaveBeenCalledWith(
          `/api/albums/${albumId}/artwork/extract`,
          expect.any(Object)
        );

        vi.clearAllMocks();
      }
    });
  });

  describe('downloadArtwork', () => {
    it('should download artwork successfully', async () => {
      const downloadResponse: ArtworkResponse = {
        message: 'Artwork downloaded from MusicBrainz',
        artwork_path: '/path/to/downloaded.jpg',
        album_id: 1,
        artist: 'Test Artist',
        album: 'Test Album',
      };

      mockPost.mockResolvedValueOnce(downloadResponse);

      const result = await downloadArtwork(1);

      expect(mockPost).toHaveBeenCalledWith(
        '/api/albums/1/artwork/download',
        expect.objectContaining({ albumId: 1 })
      );
      expect(result).toEqual(downloadResponse);
    });

    it('should throw error on failed download', async () => {
      mockPost.mockRejectedValueOnce(new Error('Album not found online'));

      await expect(downloadArtwork(1)).rejects.toThrow('Album not found online');
    });

    it('should handle API timeout', async () => {
      mockPost.mockRejectedValueOnce(new Error('Request timeout'));

      await expect(downloadArtwork(1)).rejects.toThrow('Request timeout');
    });

    it('should download for various album IDs', async () => {
      for (const albumId of [1, 42, 9999]) {
        mockPost.mockResolvedValueOnce({ message: 'Downloaded', artwork_path: '/a.jpg', album_id: albumId });

        await downloadArtwork(albumId);

        expect(mockPost).toHaveBeenCalledWith(
          `/api/albums/${albumId}/artwork/download`,
          expect.any(Object)
        );

        vi.clearAllMocks();
      }
    });
  });

  describe('deleteArtwork', () => {
    it('should delete artwork successfully', async () => {
      const deleteResponse = { message: 'Artwork deleted successfully', album_id: 1 };
      mockDel.mockResolvedValueOnce(deleteResponse);

      const result = await deleteArtwork(1);

      expect(mockDel).toHaveBeenCalledWith('/api/albums/1/artwork');
      expect(result).toEqual(deleteResponse);
    });

    it('should throw error on failed deletion', async () => {
      mockDel.mockRejectedValueOnce(new Error('Artwork not found'));

      await expect(deleteArtwork(1)).rejects.toThrow('Artwork not found');
    });

    it('should handle permission errors', async () => {
      mockDel.mockRejectedValueOnce(new Error('Permission denied'));

      await expect(deleteArtwork(1)).rejects.toThrow('Permission denied');
    });

    it('should delete for different album IDs', async () => {
      for (const albumId of [1, 100, 5000]) {
        mockDel.mockResolvedValueOnce({ message: 'Deleted', album_id: albumId });

        await deleteArtwork(albumId);

        expect(mockDel).toHaveBeenCalledWith(`/api/albums/${albumId}/artwork`);

        vi.clearAllMocks();
      }
    });
  });

  describe('Integration scenarios', () => {
    it('should handle extract -> download fallback workflow', async () => {
      mockPost.mockRejectedValueOnce(new Error('No embedded artwork'));
      await expect(extractArtwork(1)).rejects.toThrow('No embedded artwork');

      mockPost.mockResolvedValueOnce({ message: 'Downloaded from MusicBrainz', artwork_path: '/a.jpg', album_id: 1 });
      const result = await downloadArtwork(1);
      expect(result.message).toContain('Downloaded');
    });

    it('should handle extract -> delete -> re-extract workflow', async () => {
      mockPost.mockResolvedValueOnce({ message: 'Extracted', artwork_path: '/old.jpg', album_id: 1 });
      await extractArtwork(1);

      mockDel.mockResolvedValueOnce({ message: 'Deleted', album_id: 1 });
      await deleteArtwork(1);

      mockPost.mockResolvedValueOnce({ message: 'Re-extracted', artwork_path: '/new.jpg', album_id: 1 });
      const result = await extractArtwork(1);
      expect(result.message).toBe('Re-extracted');
    });

    it('should handle multiple concurrent operations', async () => {
      const albumIds = [1, 2, 3];
      albumIds.forEach(id => {
        mockPost.mockResolvedValueOnce({ message: 'Success', artwork_path: `/artwork${id}.jpg`, album_id: id });
      });

      const results = await Promise.all(albumIds.map(id => extractArtwork(id)));

      expect(results).toHaveLength(3);
      expect(results[0].album_id).toBe(1);
      expect(results[1].album_id).toBe(2);
      expect(results[2].album_id).toBe(3);
    });
  });

  describe('Error handling edge cases', () => {
    it('should handle 404 errors', async () => {
      mockPost.mockRejectedValueOnce(new Error('Album not found'));
      await expect(downloadArtwork(999999)).rejects.toThrow('Album not found');
    });

    it('should handle 500 errors', async () => {
      mockPost.mockRejectedValueOnce(new Error('Internal server error'));
      await expect(extractArtwork(1)).rejects.toThrow('Internal server error');
    });

    it('should handle timeout errors', async () => {
      mockPost.mockRejectedValueOnce(new Error('Timeout'));
      await expect(downloadArtwork(1)).rejects.toThrow('Timeout');
    });
  });
});

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
