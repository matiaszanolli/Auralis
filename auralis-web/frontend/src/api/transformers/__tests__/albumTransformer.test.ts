import { describe, it, expect } from 'vitest';
import {
  transformAlbum,
  transformAlbums,
  transformAlbumsResponse,
} from '../albumTransformer';
import type { AlbumApiResponse, AlbumsApiResponse } from '../types';
import type { Album } from '@/types/domain';

describe('albumTransformer', () => {
  describe('transformAlbum', () => {
    it('should transform complete album with all fields', () => {
      const apiAlbum: AlbumApiResponse = {
        id: 1,
        title: 'Reign in Blood',
        artist: 'Slayer',
        year: 1986,
        artwork_path: '/artwork/slayer_reign_in_blood.jpg',
        track_count: 10,
        total_duration: 1740, // 29 minutes
      };

      const result = transformAlbum(apiAlbum);

      const expected: Album = {
        id: 1,
        title: 'Reign in Blood',
        artist: 'Slayer',
        year: 1986,
        artworkUrl: '/artwork/slayer_reign_in_blood.jpg',
        trackCount: 10,
        totalDuration: 1740,
      };

      expect(result).toEqual(expected);
    });

    it('should convert null to undefined for optional fields', () => {
      const apiAlbum: AlbumApiResponse = {
        id: 2,
        title: 'Unknown Album',
        artist: 'Unknown Artist',
        year: null,
        artwork_path: null,
        track_count: 5,
        total_duration: 0,
      };

      const result = transformAlbum(apiAlbum);

      expect(result.year).toBeUndefined();
      expect(result.artworkUrl).toBeUndefined();
      expect(result.id).toBe(2);
      expect(result.trackCount).toBe(5);
    });

    it('should handle album with year but no artwork', () => {
      const apiAlbum: AlbumApiResponse = {
        id: 3,
        title: 'South of Heaven',
        artist: 'Slayer',
        year: 1988,
        artwork_path: null,
        track_count: 10,
        total_duration: 2160,
      };

      const result = transformAlbum(apiAlbum);

      expect(result.year).toBe(1988);
      expect(result.artworkUrl).toBeUndefined();
    });

    it('should handle album with artwork but no year', () => {
      const apiAlbum: AlbumApiResponse = {
        id: 4,
        title: 'Seasons in the Abyss',
        artist: 'Slayer',
        year: null,
        artwork_path: '/artwork/slayer_seasons.jpg',
        track_count: 10,
        total_duration: 2520,
      };

      const result = transformAlbum(apiAlbum);

      expect(result.year).toBeUndefined();
      expect(result.artworkUrl).toBe('/artwork/slayer_seasons.jpg');
    });

    it('should handle zero duration', () => {
      const apiAlbum: AlbumApiResponse = {
        id: 5,
        title: 'Empty Album',
        artist: 'Test Artist',
        year: 2023,
        artwork_path: '/test.jpg',
        track_count: 0,
        total_duration: 0,
      };

      const result = transformAlbum(apiAlbum);

      expect(result.totalDuration).toBe(0);
      expect(result.trackCount).toBe(0);
    });

    it('should preserve all required fields', () => {
      const apiAlbum: AlbumApiResponse = {
        id: 6,
        title: 'Test',
        artist: 'Test Artist',
        year: null,
        artwork_path: null,
        track_count: 1,
        total_duration: 100,
      };

      const result = transformAlbum(apiAlbum);

      // Required fields should always be present
      expect(result).toHaveProperty('id');
      expect(result).toHaveProperty('title');
      expect(result).toHaveProperty('artist');
      expect(result).toHaveProperty('trackCount');
    });
  });

  describe('transformAlbums', () => {
    it('should transform array of albums', () => {
      const apiAlbums: AlbumApiResponse[] = [
        {
          id: 1,
          title: 'Album 1',
          artist: 'Artist 1',
          year: 2023,
          artwork_path: '/art1.jpg',
          track_count: 10,
          total_duration: 2400,
        },
        {
          id: 2,
          title: 'Album 2',
          artist: 'Artist 2',
          year: null,
          artwork_path: null,
          track_count: 5,
          total_duration: 1200,
        },
      ];

      const result = transformAlbums(apiAlbums);

      expect(result).toHaveLength(2);
      expect(result[0].trackCount).toBe(10);
      expect(result[1].trackCount).toBe(5);
      expect(result[1].year).toBeUndefined();
    });

    it('should handle empty array', () => {
      const result = transformAlbums([]);
      expect(result).toEqual([]);
    });

    it('should handle single-item array', () => {
      const apiAlbums: AlbumApiResponse[] = [
        {
          id: 1,
          title: 'Solo Album',
          artist: 'Solo Artist',
          year: 2023,
          artwork_path: '/solo.jpg',
          track_count: 1,
          total_duration: 300,
        },
      ];

      const result = transformAlbums(apiAlbums);

      expect(result).toHaveLength(1);
      expect(result[0].trackCount).toBe(1);
    });
  });

  describe('transformAlbumsResponse', () => {
    it('should transform complete paginated response', () => {
      const apiResponse: AlbumsApiResponse = {
        albums: [
          {
            id: 1,
            title: 'Album 1',
            artist: 'Artist 1',
            year: 2023,
            artwork_path: '/art1.jpg',
            track_count: 10,
            total_duration: 2400,
          },
        ],
        total: 100,
        offset: 0,
        limit: 50,
        has_more: true,
      };

      const result = transformAlbumsResponse(apiResponse);

      expect(result.albums).toHaveLength(1);
      expect(result.total).toBe(100);
      expect(result.offset).toBe(0);
      expect(result.limit).toBe(50);
      expect(result.hasMore).toBe(true);
    });

    it('should handle last page (has_more false)', () => {
      const apiResponse: AlbumsApiResponse = {
        albums: [],
        total: 50,
        offset: 50,
        limit: 50,
        has_more: false,
      };

      const result = transformAlbumsResponse(apiResponse);

      expect(result.albums).toEqual([]);
      expect(result.hasMore).toBe(false);
    });

    it('should convert snake_case pagination fields to camelCase', () => {
      const apiResponse: AlbumsApiResponse = {
        albums: [],
        total: 0,
        offset: 0,
        limit: 50,
        has_more: false,
      };

      const result = transformAlbumsResponse(apiResponse);

      // Verify camelCase conversion
      expect(result).toHaveProperty('hasMore');
      expect(result).not.toHaveProperty('has_more');
    });

    it('should preserve pagination metadata', () => {
      const apiResponse: AlbumsApiResponse = {
        albums: [
          {
            id: 1,
            title: 'Test',
            artist: 'Test',
            year: null,
            artwork_path: null,
            track_count: 1,
            total_duration: 100,
          },
        ],
        total: 1000,
        offset: 200,
        limit: 100,
        has_more: true,
      };

      const result = transformAlbumsResponse(apiResponse);

      expect(result.total).toBe(1000);
      expect(result.offset).toBe(200);
      expect(result.limit).toBe(100);
    });
  });

  describe('field name conversions', () => {
    it('should convert artwork_path to artworkUrl', () => {
      const apiAlbum: AlbumApiResponse = {
        id: 1,
        title: 'Test',
        artist: 'Test',
        year: null,
        artwork_path: '/test.jpg',
        track_count: 1,
        total_duration: 100,
      };

      const result = transformAlbum(apiAlbum);

      expect(result.artworkUrl).toBe('/test.jpg');
      expect(result).not.toHaveProperty('artwork_path');
    });

    it('should convert track_count to trackCount', () => {
      const apiAlbum: AlbumApiResponse = {
        id: 1,
        title: 'Test',
        artist: 'Test',
        year: null,
        artwork_path: null,
        track_count: 42,
        total_duration: 100,
      };

      const result = transformAlbum(apiAlbum);

      expect(result.trackCount).toBe(42);
      expect(result).not.toHaveProperty('track_count');
    });

    it('should convert total_duration to totalDuration', () => {
      const apiAlbum: AlbumApiResponse = {
        id: 1,
        title: 'Test',
        artist: 'Test',
        year: null,
        artwork_path: null,
        track_count: 1,
        total_duration: 3600,
      };

      const result = transformAlbum(apiAlbum);

      expect(result.totalDuration).toBe(3600);
      expect(result).not.toHaveProperty('total_duration');
    });
  });

  describe('type safety', () => {
    it('should produce Album type from transformation', () => {
      const apiAlbum: AlbumApiResponse = {
        id: 1,
        title: 'Test',
        artist: 'Test',
        year: 2023,
        artwork_path: '/test.jpg',
        track_count: 10,
        total_duration: 2400,
      };

      const result: Album = transformAlbum(apiAlbum);

      // TypeScript should accept this assignment without errors
      expect(result.id).toBe(1);
    });

    it('should produce Album[] type from array transformation', () => {
      const apiAlbums: AlbumApiResponse[] = [
        {
          id: 1,
          title: 'Test',
          artist: 'Test',
          year: null,
          artwork_path: null,
          track_count: 1,
          total_duration: 100,
        },
      ];

      const result: Album[] = transformAlbums(apiAlbums);

      // TypeScript should accept this assignment without errors
      expect(result).toHaveLength(1);
    });
  });
});
