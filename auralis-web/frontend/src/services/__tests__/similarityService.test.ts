/**
 * SimilarityService Unit Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tests for the TypeScript API client for the similarity system
 *
 * Test Coverage:
 * - API call methods (findSimilar, compareTracks, explainSimilarity)
 * - Graph management (buildGraph, getGraphStats)
 * - System initialization (fit, isReady)
 * - Error handling
 * - Response parsing
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import similarityService, {
  SimilarTrack,
  ComparisonResult,
  SimilarityExplanation,
  GraphStats,
  FitResult
} from '../similarityService';

// Mock fetch globally
global.fetch = vi.fn();

describe('SimilarityService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  describe('findSimilar', () => {
    it('should find similar tracks with default parameters', async () => {
      const mockResponse: SimilarTrack[] = [
        {
          track_id: 2,
          distance: 0.123,
          similarity_score: 0.85,
          title: 'Similar Track',
          artist: 'Artist Name',
          album: 'Album Name',
          duration: 240
        }
      ];

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const result = await similarityService.findSimilar(1);

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/similarity/tracks/1/similar?limit=10&use_graph=true'
      );
      expect(result).toEqual(mockResponse);
      expect(result[0].track_id).toBe(2);
      expect(result[0].similarity_score).toBe(0.85);
    });

    it('should find similar tracks with custom limit', async () => {
      const mockResponse: SimilarTrack[] = [];

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      await similarityService.findSimilar(1, 5);

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/similarity/tracks/1/similar?limit=5&use_graph=true'
      );
    });

    it('should find similar tracks without graph', async () => {
      const mockResponse: SimilarTrack[] = [];

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      await similarityService.findSimilar(1, 10, false);

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/similarity/tracks/1/similar?limit=10&use_graph=false'
      );
    });

    it('should throw error on API failure', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: 'Not Found'
      });

      await expect(similarityService.findSimilar(999999))
        .rejects.toThrow('Failed to find similar tracks: 404 Not Found');
    });

    it('should throw error on network failure', async () => {
      (global.fetch as any).mockRejectedValueOnce(new Error('Network error'));

      await expect(similarityService.findSimilar(1))
        .rejects.toThrow('Network error');
    });
  });

  describe('compareTracks', () => {
    it('should compare two tracks', async () => {
      const mockResponse: ComparisonResult = {
        track_id1: 1,
        track_id2: 2,
        distance: 0.456,
        similarity_score: 0.72
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const result = await similarityService.compareTracks(1, 2);

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/similarity/tracks/1/compare/2'
      );
      expect(result).toEqual(mockResponse);
      expect(result.track_id1).toBe(1);
      expect(result.track_id2).toBe(2);
      expect(result.distance).toBe(0.456);
    });

    it('should handle same track comparison', async () => {
      const mockResponse: ComparisonResult = {
        track_id1: 1,
        track_id2: 1,
        distance: 0.0,
        similarity_score: 1.0
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const result = await similarityService.compareTracks(1, 1);

      expect(result.distance).toBe(0.0);
      expect(result.similarity_score).toBe(1.0);
    });

    it('should throw error on invalid track IDs', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: 'Track not found'
      });

      await expect(similarityService.compareTracks(999999, 999998))
        .rejects.toThrow('Failed to compare tracks: 404 Track not found');
    });
  });

  describe('explainSimilarity', () => {
    it('should explain similarity between tracks', async () => {
      const mockResponse: SimilarityExplanation = {
        track_id1: 1,
        track_id2: 2,
        distance: 0.456,
        similarity_score: 0.72,
        top_differences: [
          {
            dimension: 'bass_pct',
            contribution: 0.125,
            value1: 45.2,
            value2: 60.1,
            difference: 14.9
          }
        ],
        all_contributions: [
          { dimension: 'bass_pct', contribution: 0.125 }
        ]
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const result = await similarityService.explainSimilarity(1, 2, 5);

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/similarity/tracks/1/explain/2?top_n=5'
      );
      expect(result).toEqual(mockResponse);
      expect(result.top_differences).toHaveLength(1);
      expect(result.top_differences[0].dimension).toBe('bass_pct');
    });

    it('should use default topN parameter', async () => {
      const mockResponse: SimilarityExplanation = {
        track_id1: 1,
        track_id2: 2,
        distance: 0.456,
        similarity_score: 0.72,
        top_differences: [],
        all_contributions: []
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      await similarityService.explainSimilarity(1, 2);

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/similarity/tracks/1/explain/2?top_n=5'
      );
    });
  });

  describe('buildGraph', () => {
    it('should build K-NN graph with default k', async () => {
      const mockResponse: GraphStats = {
        total_tracks: 100,
        total_edges: 1000,
        k_neighbors: 10,
        avg_distance: 0.345,
        build_time_seconds: 2.5
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const result = await similarityService.buildGraph();

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/similarity/graph/build?k=10',
        { method: 'POST' }
      );
      expect(result).toEqual(mockResponse);
      expect(result.k_neighbors).toBe(10);
    });

    it('should build K-NN graph with custom k', async () => {
      const mockResponse: GraphStats = {
        total_tracks: 100,
        total_edges: 500,
        k_neighbors: 5,
        avg_distance: 0.345,
        build_time_seconds: 1.2
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      await similarityService.buildGraph(5);

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/similarity/graph/build?k=5',
        { method: 'POST' }
      );
    });

    it('should throw error if insufficient fingerprints', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 400,
        statusText: 'Insufficient fingerprints'
      });

      await expect(similarityService.buildGraph())
        .rejects.toThrow('Failed to build graph: 400 Insufficient fingerprints');
    });
  });

  describe('getGraphStats', () => {
    it('should get graph statistics', async () => {
      const mockResponse: GraphStats = {
        total_tracks: 100,
        total_edges: 1000,
        k_neighbors: 10,
        avg_distance: 0.345
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const result = await similarityService.getGraphStats();

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/similarity/graph/stats'
      );
      expect(result).toEqual(mockResponse);
    });

    it('should return null if no graph exists', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: 'Graph not built'
      });

      const result = await similarityService.getGraphStats();

      expect(result).toBeNull();
    });
  });

  describe('fit', () => {
    it('should fit similarity system with default parameters', async () => {
      const mockResponse: FitResult = {
        fitted: true,
        total_fingerprints: 50
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const result = await similarityService.fit();

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/similarity/fit?min_samples=10',
        { method: 'POST' }
      );
      expect(result).toEqual(mockResponse);
      expect(result.fitted).toBe(true);
    });

    it('should fit with custom min_samples', async () => {
      const mockResponse: FitResult = {
        fitted: true,
        total_fingerprints: 100
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      await similarityService.fit(20);

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/similarity/fit?min_samples=20',
        { method: 'POST' }
      );
    });

    it('should handle insufficient fingerprints', async () => {
      const mockResponse: FitResult = {
        fitted: false,
        total_fingerprints: 5
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const result = await similarityService.fit(10);

      expect(result.fitted).toBe(false);
    });
  });

  describe('isReady', () => {
    it('should return true when system is ready', async () => {
      const mockGraphStats: GraphStats = {
        total_tracks: 100,
        total_edges: 1000,
        k_neighbors: 10,
        avg_distance: 0.345
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockGraphStats
      });

      const result = await similarityService.isReady();

      expect(result).toBe(true);
    });

    it('should return false when no graph exists', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 404
      });

      const result = await similarityService.isReady();

      expect(result).toBe(false);
    });

    it('should return false on network error', async () => {
      (global.fetch as any).mockRejectedValueOnce(new Error('Network error'));

      const result = await similarityService.isReady();

      expect(result).toBe(false);
    });
  });
});
