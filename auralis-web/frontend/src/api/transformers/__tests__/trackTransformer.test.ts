import { describe, it, expect } from 'vitest';
import {
  transformTrack,
  transformTracks,
  transformTracksResponse,
} from '../trackTransformer';
import type { TrackApiResponse, TracksApiResponse } from '../types';
import type { Track } from '@/types/domain';

describe('trackTransformer', () => {
  describe('transformTrack', () => {
    it('should transform complete track with all fields', () => {
      const apiTrack: TrackApiResponse = {
        id: 1,
        title: 'Angel of Death',
        artist: 'Slayer',
        album: 'Reign in Blood',
        duration: 286,
        filepath: '/music/slayer/reign_in_blood/01_angel_of_death.flac',
        artwork_url: '/artwork/slayer_reign_in_blood.jpg',
        genre: 'Thrash Metal',
        year: 1986,
        bitrate: 1411,
        sample_rate: 48000,
        bit_depth: 24,
        format: 'flac',
        loudness: -8.5,
        crest_factor: 12.3,
        centroid: 2500,
        date_added: '2023-01-15T10:30:00Z',
        date_modified: '2023-02-20T14:15:00Z',
      };

      const result = transformTrack(apiTrack);

      const expected: Track = {
        id: 1,
        title: 'Angel of Death',
        artist: 'Slayer',
        album: 'Reign in Blood',
        duration: 286,
        filepath: '/music/slayer/reign_in_blood/01_angel_of_death.flac',
        artworkUrl: '/artwork/slayer_reign_in_blood.jpg',
        genre: 'Thrash Metal',
        year: 1986,
        bitrate: 1411,
        sampleRate: 48000,
        bitDepth: 24,
        format: 'flac',
        loudness: -8.5,
        crestFactor: 12.3,
        centroid: 2500,
        dateAdded: '2023-01-15T10:30:00Z',
        dateModified: '2023-02-20T14:15:00Z',
      };

      expect(result).toEqual(expected);
    });

    it('should convert null to undefined for optional fields', () => {
      const apiTrack: TrackApiResponse = {
        id: 2,
        title: 'Unknown Track',
        artist: 'Unknown Artist',
        album: 'Unknown Album',
        duration: 180,
        filepath: '/music/unknown.mp3',
        artwork_url: null,
        genre: null,
        year: null,
        bitrate: null,
        sample_rate: null,
        bit_depth: null,
        format: null,
        loudness: null,
        crest_factor: null,
        centroid: null,
        date_added: null,
        date_modified: null,
      };

      const result = transformTrack(apiTrack);

      expect(result.artworkUrl).toBeUndefined();
      expect(result.genre).toBeUndefined();
      expect(result.year).toBeUndefined();
      expect(result.bitrate).toBeUndefined();
      expect(result.sampleRate).toBeUndefined();
      expect(result.bitDepth).toBeUndefined();
      expect(result.format).toBeUndefined();
      expect(result.loudness).toBeUndefined();
      expect(result.crestFactor).toBeUndefined();
      expect(result.centroid).toBeUndefined();
      expect(result.dateAdded).toBeUndefined();
      expect(result.dateModified).toBeUndefined();
    });

    it('should handle track with minimal metadata', () => {
      const apiTrack: TrackApiResponse = {
        id: 3,
        title: 'Simple Track',
        artist: 'Simple Artist',
        album: 'Simple Album',
        duration: 120,
        filepath: '/simple.mp3',
        artwork_url: null,
        genre: null,
        year: null,
        bitrate: null,
        sample_rate: null,
        bit_depth: null,
        format: null,
        loudness: null,
        crest_factor: null,
        centroid: null,
        date_added: null,
        date_modified: null,
      };

      const result = transformTrack(apiTrack);

      expect(result.id).toBe(3);
      expect(result.title).toBe('Simple Track');
      expect(result.duration).toBe(120);
    });

    it('should handle track with high-resolution audio specs', () => {
      const apiTrack: TrackApiResponse = {
        id: 4,
        title: 'HiRes Track',
        artist: 'HiRes Artist',
        album: 'HiRes Album',
        duration: 300,
        filepath: '/hires.flac',
        artwork_url: '/hires.jpg',
        genre: null,
        year: null,
        bitrate: 2822,
        sample_rate: 96000,
        bit_depth: 32,
        format: 'flac',
        loudness: null,
        crest_factor: null,
        centroid: null,
        date_added: null,
        date_modified: null,
      };

      const result = transformTrack(apiTrack);

      expect(result.sampleRate).toBe(96000);
      expect(result.bitDepth).toBe(32);
      expect(result.bitrate).toBe(2822);
      expect(result.format).toBe('flac');
    });

    it('should preserve all required fields', () => {
      const apiTrack: TrackApiResponse = {
        id: 5,
        title: 'Test',
        artist: 'Test',
        album: 'Test',
        duration: 100,
        filepath: '/test.mp3',
        artwork_url: null,
        genre: null,
        year: null,
        bitrate: null,
        sample_rate: null,
        bit_depth: null,
        format: null,
        loudness: null,
        crest_factor: null,
        centroid: null,
        date_added: null,
        date_modified: null,
      };

      const result = transformTrack(apiTrack);

      // Required fields should always be present
      expect(result).toHaveProperty('id');
      expect(result).toHaveProperty('title');
      expect(result).toHaveProperty('artist');
      expect(result).toHaveProperty('album');
      expect(result).toHaveProperty('duration');
      expect(result).toHaveProperty('filepath');
    });
  });

  describe('transformTracks', () => {
    it('should transform array of tracks', () => {
      const apiTracks: TrackApiResponse[] = [
        {
          id: 1,
          title: 'Track 1',
          artist: 'Artist 1',
          album: 'Album 1',
          duration: 180,
          filepath: '/track1.mp3',
          artwork_url: '/art1.jpg',
          genre: 'Rock',
          year: 2023,
          bitrate: 320,
          sample_rate: 44100,
          bit_depth: 16,
          format: 'mp3',
          loudness: -10.0,
          crest_factor: 10.5,
          centroid: 2000,
          date_added: '2023-01-01T00:00:00Z',
          date_modified: null,
        },
        {
          id: 2,
          title: 'Track 2',
          artist: 'Artist 2',
          album: 'Album 2',
          duration: 200,
          filepath: '/track2.flac',
          artwork_url: null,
          genre: null,
          year: null,
          bitrate: null,
          sample_rate: null,
          bit_depth: null,
          format: null,
          loudness: null,
          crest_factor: null,
          centroid: null,
          date_added: null,
          date_modified: null,
        },
      ];

      const result = transformTracks(apiTracks);

      expect(result).toHaveLength(2);
      expect(result[0].sampleRate).toBe(44100);
      expect(result[1].sampleRate).toBeUndefined();
    });

    it('should handle empty array', () => {
      const result = transformTracks([]);
      expect(result).toEqual([]);
    });

    it('should handle single-item array', () => {
      const apiTracks: TrackApiResponse[] = [
        {
          id: 1,
          title: 'Solo Track',
          artist: 'Solo',
          album: 'Solo',
          duration: 150,
          filepath: '/solo.mp3',
          artwork_url: null,
          genre: null,
          year: null,
          bitrate: null,
          sample_rate: null,
          bit_depth: null,
          format: null,
          loudness: null,
          crest_factor: null,
          centroid: null,
          date_added: null,
          date_modified: null,
        },
      ];

      const result = transformTracks(apiTracks);

      expect(result).toHaveLength(1);
      expect(result[0].title).toBe('Solo Track');
    });
  });

  describe('transformTracksResponse', () => {
    it('should transform complete paginated response', () => {
      const apiResponse: TracksApiResponse = {
        tracks: [
          {
            id: 1,
            title: 'Track 1',
            artist: 'Artist 1',
            album: 'Album 1',
            duration: 180,
            filepath: '/track1.mp3',
            artwork_url: null,
            genre: null,
            year: null,
            bitrate: null,
            sample_rate: null,
            bit_depth: null,
            format: null,
            loudness: null,
            crest_factor: null,
            centroid: null,
            date_added: null,
            date_modified: null,
          },
        ],
        total: 500,
        offset: 0,
        limit: 100,
        has_more: true,
      };

      const result = transformTracksResponse(apiResponse);

      expect(result.tracks).toHaveLength(1);
      expect(result.total).toBe(500);
      expect(result.offset).toBe(0);
      expect(result.limit).toBe(100);
      expect(result.hasMore).toBe(true);
    });

    it('should handle last page (has_more false)', () => {
      const apiResponse: TracksApiResponse = {
        tracks: [],
        total: 100,
        offset: 100,
        limit: 100,
        has_more: false,
      };

      const result = transformTracksResponse(apiResponse);

      expect(result.tracks).toEqual([]);
      expect(result.hasMore).toBe(false);
    });

    it('should convert snake_case pagination fields to camelCase', () => {
      const apiResponse: TracksApiResponse = {
        tracks: [],
        total: 0,
        offset: 0,
        limit: 100,
        has_more: false,
      };

      const result = transformTracksResponse(apiResponse);

      // Verify camelCase conversion
      expect(result).toHaveProperty('hasMore');
      expect(result).not.toHaveProperty('has_more');
    });

    it('should preserve pagination metadata', () => {
      const apiResponse: TracksApiResponse = {
        tracks: [
          {
            id: 1,
            title: 'Test',
            artist: 'Test',
            album: 'Test',
            duration: 100,
            filepath: '/test.mp3',
            artwork_url: null,
            genre: null,
            year: null,
            bitrate: null,
            sample_rate: null,
            bit_depth: null,
            format: null,
            loudness: null,
            crest_factor: null,
            centroid: null,
            date_added: null,
            date_modified: null,
          },
        ],
        total: 5000,
        offset: 500,
        limit: 100,
        has_more: true,
      };

      const result = transformTracksResponse(apiResponse);

      expect(result.total).toBe(5000);
      expect(result.offset).toBe(500);
      expect(result.limit).toBe(100);
    });
  });

  describe('field name conversions', () => {
    it('should convert artwork_url to artworkUrl', () => {
      const apiTrack: TrackApiResponse = {
        id: 1,
        title: 'Test',
        artist: 'Test',
        album: 'Test',
        duration: 100,
        filepath: '/test.mp3',
        artwork_url: '/test.jpg',
        genre: null,
        year: null,
        bitrate: null,
        sample_rate: null,
        bit_depth: null,
        format: null,
        loudness: null,
        crest_factor: null,
        centroid: null,
        date_added: null,
        date_modified: null,
      };

      const result = transformTrack(apiTrack);

      expect(result.artworkUrl).toBe('/test.jpg');
      expect(result).not.toHaveProperty('artwork_url');
    });

    it('should convert sample_rate to sampleRate', () => {
      const apiTrack: TrackApiResponse = {
        id: 1,
        title: 'Test',
        artist: 'Test',
        album: 'Test',
        duration: 100,
        filepath: '/test.mp3',
        artwork_url: null,
        genre: null,
        year: null,
        bitrate: null,
        sample_rate: 48000,
        bit_depth: null,
        format: null,
        loudness: null,
        crest_factor: null,
        centroid: null,
        date_added: null,
        date_modified: null,
      };

      const result = transformTrack(apiTrack);

      expect(result.sampleRate).toBe(48000);
      expect(result).not.toHaveProperty('sample_rate');
    });

    it('should convert bit_depth to bitDepth', () => {
      const apiTrack: TrackApiResponse = {
        id: 1,
        title: 'Test',
        artist: 'Test',
        album: 'Test',
        duration: 100,
        filepath: '/test.mp3',
        artwork_url: null,
        genre: null,
        year: null,
        bitrate: null,
        sample_rate: null,
        bit_depth: 24,
        format: null,
        loudness: null,
        crest_factor: null,
        centroid: null,
        date_added: null,
        date_modified: null,
      };

      const result = transformTrack(apiTrack);

      expect(result.bitDepth).toBe(24);
      expect(result).not.toHaveProperty('bit_depth');
    });

    it('should convert crest_factor to crestFactor', () => {
      const apiTrack: TrackApiResponse = {
        id: 1,
        title: 'Test',
        artist: 'Test',
        album: 'Test',
        duration: 100,
        filepath: '/test.mp3',
        artwork_url: null,
        genre: null,
        year: null,
        bitrate: null,
        sample_rate: null,
        bit_depth: null,
        format: null,
        loudness: null,
        crest_factor: 15.2,
        centroid: null,
        date_added: null,
        date_modified: null,
      };

      const result = transformTrack(apiTrack);

      expect(result.crestFactor).toBe(15.2);
      expect(result).not.toHaveProperty('crest_factor');
    });

    it('should convert date_added to dateAdded', () => {
      const apiTrack: TrackApiResponse = {
        id: 1,
        title: 'Test',
        artist: 'Test',
        album: 'Test',
        duration: 100,
        filepath: '/test.mp3',
        artwork_url: null,
        genre: null,
        year: null,
        bitrate: null,
        sample_rate: null,
        bit_depth: null,
        format: null,
        loudness: null,
        crest_factor: null,
        centroid: null,
        date_added: '2023-12-25T12:00:00Z',
        date_modified: null,
      };

      const result = transformTrack(apiTrack);

      expect(result.dateAdded).toBe('2023-12-25T12:00:00Z');
      expect(result).not.toHaveProperty('date_added');
    });

    it('should convert date_modified to dateModified', () => {
      const apiTrack: TrackApiResponse = {
        id: 1,
        title: 'Test',
        artist: 'Test',
        album: 'Test',
        duration: 100,
        filepath: '/test.mp3',
        artwork_url: null,
        genre: null,
        year: null,
        bitrate: null,
        sample_rate: null,
        bit_depth: null,
        format: null,
        loudness: null,
        crest_factor: null,
        centroid: null,
        date_added: null,
        date_modified: '2024-01-15T08:30:00Z',
      };

      const result = transformTrack(apiTrack);

      expect(result.dateModified).toBe('2024-01-15T08:30:00Z');
      expect(result).not.toHaveProperty('date_modified');
    });
  });

  describe('type safety', () => {
    it('should produce Track type from transformation', () => {
      const apiTrack: TrackApiResponse = {
        id: 1,
        title: 'Test Track',
        artist: 'Test Artist',
        album: 'Test Album',
        duration: 180,
        filepath: '/test.mp3',
        artwork_url: '/test.jpg',
        genre: 'Rock',
        year: 2023,
        bitrate: 320,
        sample_rate: 44100,
        bit_depth: 16,
        format: 'mp3',
        loudness: -10.0,
        crest_factor: 12.0,
        centroid: 2000,
        date_added: '2023-01-01T00:00:00Z',
        date_modified: null,
      };

      const result: Track = transformTrack(apiTrack);

      // TypeScript should accept this assignment without errors
      expect(result.id).toBe(1);
    });

    it('should produce Track[] type from array transformation', () => {
      const apiTracks: TrackApiResponse[] = [
        {
          id: 1,
          title: 'Test',
          artist: 'Test',
          album: 'Test',
          duration: 100,
          filepath: '/test.mp3',
          artwork_url: null,
          genre: null,
          year: null,
          bitrate: null,
          sample_rate: null,
          bit_depth: null,
          format: null,
          loudness: null,
          crest_factor: null,
          centroid: null,
          date_added: null,
          date_modified: null,
        },
      ];

      const result: Track[] = transformTracks(apiTracks);

      // TypeScript should accept this assignment without errors
      expect(result).toHaveLength(1);
    });
  });
});
