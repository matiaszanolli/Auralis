import { describe, it, expect } from 'vitest';
import {
  transformArtist,
  transformArtists,
  transformArtistsResponse,
} from '../artistTransformer';
import type { ArtistApiResponse, ArtistsApiResponse } from '../types';
import type { Artist } from '@/types/domain';

describe('artistTransformer', () => {
  describe('transformArtist', () => {
    it('should transform complete artist with all fields', () => {
      const apiArtist: ArtistApiResponse = {
        id: 1,
        name: 'Slayer',
        artwork_url: '/artists/slayer.jpg',
        track_count: 120,
        album_count: 12,
        date_added: '2023-01-15T10:30:00Z',
      };

      const result = transformArtist(apiArtist);

      const expected: Artist = {
        id: 1,
        name: 'Slayer',
        artworkUrl: '/artists/slayer.jpg',
        trackCount: 120,
        albumCount: 12,
        dateAdded: '2023-01-15T10:30:00Z',
      };

      expect(result).toEqual(expected);
    });

    it('should convert null to undefined for optional fields', () => {
      const apiArtist: ArtistApiResponse = {
        id: 2,
        name: 'Unknown Artist',
        artwork_url: null,
        track_count: 5,
        album_count: 1,
        date_added: null,
      };

      const result = transformArtist(apiArtist);

      expect(result.artworkUrl).toBeUndefined();
      expect(result.dateAdded).toBeUndefined();
      expect(result.name).toBe('Unknown Artist');
      expect(result.trackCount).toBe(5);
      expect(result.albumCount).toBe(1);
    });

    it('should handle artist with no albums', () => {
      const apiArtist: ArtistApiResponse = {
        id: 3,
        name: 'New Artist',
        artwork_url: '/new.jpg',
        track_count: 0,
        album_count: 0,
        date_added: '2024-12-01T00:00:00Z',
      };

      const result = transformArtist(apiArtist);

      expect(result.trackCount).toBe(0);
      expect(result.albumCount).toBe(0);
    });

    it('should handle artist with artwork but no date', () => {
      const apiArtist: ArtistApiResponse = {
        id: 4,
        name: 'Metallica',
        artwork_url: '/metallica.jpg',
        track_count: 150,
        album_count: 10,
        date_added: null,
      };

      const result = transformArtist(apiArtist);

      expect(result.artworkUrl).toBe('/metallica.jpg');
      expect(result.dateAdded).toBeUndefined();
    });

    it('should preserve all required fields', () => {
      const apiArtist: ArtistApiResponse = {
        id: 5,
        name: 'Test Artist',
        artwork_url: null,
        track_count: 1,
        album_count: 1,
        date_added: null,
      };

      const result = transformArtist(apiArtist);

      // Required fields should always be present
      expect(result).toHaveProperty('id');
      expect(result).toHaveProperty('name');
      expect(result).toHaveProperty('trackCount');
      expect(result).toHaveProperty('albumCount');
    });
  });

  describe('transformArtists', () => {
    it('should transform array of artists', () => {
      const apiArtists: ArtistApiResponse[] = [
        {
          id: 1,
          name: 'Artist 1',
          artwork_url: '/art1.jpg',
          track_count: 50,
          album_count: 5,
          date_added: '2023-01-01T00:00:00Z',
        },
        {
          id: 2,
          name: 'Artist 2',
          artwork_url: null,
          track_count: 20,
          album_count: 2,
          date_added: null,
        },
      ];

      const result = transformArtists(apiArtists);

      expect(result).toHaveLength(2);
      expect(result[0].trackCount).toBe(50);
      expect(result[1].trackCount).toBe(20);
      expect(result[1].artworkUrl).toBeUndefined();
    });

    it('should handle empty array', () => {
      const result = transformArtists([]);
      expect(result).toEqual([]);
    });

    it('should handle single-item array', () => {
      const apiArtists: ArtistApiResponse[] = [
        {
          id: 1,
          name: 'Solo Artist',
          artwork_url: '/solo.jpg',
          track_count: 10,
          album_count: 1,
          date_added: '2023-01-01T00:00:00Z',
        },
      ];

      const result = transformArtists(apiArtists);

      expect(result).toHaveLength(1);
      expect(result[0].name).toBe('Solo Artist');
    });
  });

  describe('transformArtistsResponse', () => {
    it('should transform complete paginated response', () => {
      const apiResponse: ArtistsApiResponse = {
        artists: [
          {
            id: 1,
            name: 'Artist 1',
            artwork_url: '/art1.jpg',
            track_count: 50,
            album_count: 5,
            date_added: '2023-01-01T00:00:00Z',
          },
        ],
        total: 200,
        offset: 0,
        limit: 50,
        has_more: true,
      };

      const result = transformArtistsResponse(apiResponse);

      expect(result.artists).toHaveLength(1);
      expect(result.total).toBe(200);
      expect(result.offset).toBe(0);
      expect(result.limit).toBe(50);
      expect(result.hasMore).toBe(true);
    });

    it('should handle last page (has_more false)', () => {
      const apiResponse: ArtistsApiResponse = {
        artists: [],
        total: 50,
        offset: 50,
        limit: 50,
        has_more: false,
      };

      const result = transformArtistsResponse(apiResponse);

      expect(result.artists).toEqual([]);
      expect(result.hasMore).toBe(false);
    });

    it('should convert snake_case pagination fields to camelCase', () => {
      const apiResponse: ArtistsApiResponse = {
        artists: [],
        total: 0,
        offset: 0,
        limit: 50,
        has_more: false,
      };

      const result = transformArtistsResponse(apiResponse);

      // Verify camelCase conversion
      expect(result).toHaveProperty('hasMore');
      expect(result).not.toHaveProperty('has_more');
    });

    it('should preserve pagination metadata', () => {
      const apiResponse: ArtistsApiResponse = {
        artists: [
          {
            id: 1,
            name: 'Test',
            artwork_url: null,
            track_count: 1,
            album_count: 1,
            date_added: null,
          },
        ],
        total: 1000,
        offset: 300,
        limit: 100,
        has_more: true,
      };

      const result = transformArtistsResponse(apiResponse);

      expect(result.total).toBe(1000);
      expect(result.offset).toBe(300);
      expect(result.limit).toBe(100);
    });
  });

  describe('field name conversions', () => {
    it('should convert artwork_url (backend) to artworkUrl (domain)', () => {
      const apiArtist: ArtistApiResponse = {
        id: 1,
        name: 'Test',
        artwork_url: '/test.jpg',
        track_count: 1,
        album_count: 1,
        date_added: null,
      };

      const result = transformArtist(apiArtist);

      expect(result.artworkUrl).toBe('/test.jpg');
      expect(result).not.toHaveProperty('artwork_url');
    });

    it('should convert track_count to trackCount', () => {
      const apiArtist: ArtistApiResponse = {
        id: 1,
        name: 'Test',
        artwork_url: null,
        track_count: 99,
        album_count: 1,
        date_added: null,
      };

      const result = transformArtist(apiArtist);

      expect(result.trackCount).toBe(99);
      expect(result).not.toHaveProperty('track_count');
    });

    it('should convert album_count to albumCount', () => {
      const apiArtist: ArtistApiResponse = {
        id: 1,
        name: 'Test',
        artwork_url: null,
        track_count: 1,
        album_count: 15,
        date_added: null,
      };

      const result = transformArtist(apiArtist);

      expect(result.albumCount).toBe(15);
      expect(result).not.toHaveProperty('album_count');
    });

    it('should convert date_added to dateAdded', () => {
      const apiArtist: ArtistApiResponse = {
        id: 1,
        name: 'Test',
        artwork_url: null,
        track_count: 1,
        album_count: 1,
        date_added: '2023-12-25T12:00:00Z',
      };

      const result = transformArtist(apiArtist);

      expect(result.dateAdded).toBe('2023-12-25T12:00:00Z');
      expect(result).not.toHaveProperty('date_added');
    });
  });

  describe('type safety', () => {
    it('should produce Artist type from transformation', () => {
      const apiArtist: ArtistApiResponse = {
        id: 1,
        name: 'Test Artist',
        artwork_url: '/test.jpg',
        track_count: 50,
        album_count: 5,
        date_added: '2023-01-01T00:00:00Z',
      };

      const result: Artist = transformArtist(apiArtist);

      // TypeScript should accept this assignment without errors
      expect(result.id).toBe(1);
    });

    it('should produce Artist[] type from array transformation', () => {
      const apiArtists: ArtistApiResponse[] = [
        {
          id: 1,
          name: 'Test',
          artwork_url: null,
          track_count: 1,
          album_count: 1,
          date_added: null,
        },
      ];

      const result: Artist[] = transformArtists(apiArtists);

      // TypeScript should accept this assignment without errors
      expect(result).toHaveLength(1);
    });
  });
});
