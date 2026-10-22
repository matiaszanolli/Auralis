import { describe, it, expect } from 'vitest';
import {
  transformArtist,
  transformArtists,
} from '../artistTransformer';
import type { ArtistApiResponse } from '../types';
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
        created_at: '2023-01-15T10:30:00Z',
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
        created_at: null,
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
        created_at: '2024-12-01T00:00:00Z',
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
        created_at: null,
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
        created_at: null,
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
          created_at: '2023-01-01T00:00:00Z',
        },
        {
          id: 2,
          name: 'Artist 2',
          artwork_url: null,
          track_count: 20,
          album_count: 2,
          created_at: null,
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
          created_at: '2023-01-01T00:00:00Z',
        },
      ];

      const result = transformArtists(apiArtists);

      expect(result).toHaveLength(1);
      expect(result[0].name).toBe('Solo Artist');
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
        created_at: null,
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
        created_at: null,
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
        created_at: null,
      };

      const result = transformArtist(apiArtist);

      expect(result.albumCount).toBe(15);
      expect(result).not.toHaveProperty('album_count');
    });

    it('should convert created_at to dateAdded (#4833)', () => {
      const apiArtist: ArtistApiResponse = {
        id: 1,
        name: 'Test',
        artwork_url: null,
        track_count: 1,
        album_count: 1,
        created_at: '2023-12-25T12:00:00Z',
      };

      const result = transformArtist(apiArtist);

      expect(result.dateAdded).toBe('2023-12-25T12:00:00Z');
      expect(result).not.toHaveProperty('created_at');
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
        created_at: '2023-01-01T00:00:00Z',
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
          created_at: null,
        },
      ];

      const result: Artist[] = transformArtists(apiArtists);

      // TypeScript should accept this assignment without errors
      expect(result).toHaveLength(1);
    });
  });
});
