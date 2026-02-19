/**
 * SimilarityService Unit Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tests for the TypeScript API client for the similarity system.
 * Mocks at the apiRequest module level to avoid MSW conflicts.
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

import { get, post, APIRequestError } from '../../utils/apiRequest';
import similarityService, {
  type SimilarTrack,
  type ComparisonResult,
  type SimilarityExplanation,
  type GraphStats,
  type FitResult,
} from '../similarityService';

const mockGet = get as ReturnType<typeof vi.fn>;
const mockPost = post as ReturnType<typeof vi.fn>;

const mockGraphStats: GraphStats = {
  total_tracks: 100,
  total_edges: 1000,
  k_neighbors: 10,
  avg_distance: 0.345,
  min_distance: 0.001,
  max_distance: 0.890,
  build_time_seconds: 2.5,
};

describe('SimilarityService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
          duration: 240,
        },
      ];
      mockGet.mockResolvedValueOnce(mockResponse);

      const result = await similarityService.findSimilar(1);

      expect(mockGet).toHaveBeenCalledWith('/similarity/tracks/1/similar?limit=10&use_graph=true');
      expect(result).toEqual(mockResponse);
      expect(result[0].track_id).toBe(2);
      expect(result[0].similarity_score).toBe(0.85);
    });

    it('should find similar tracks with custom limit', async () => {
      mockGet.mockResolvedValueOnce([]);

      await similarityService.findSimilar(1, 5);

      expect(mockGet).toHaveBeenCalledWith('/similarity/tracks/1/similar?limit=5&use_graph=true');
    });

    it('should find similar tracks without graph', async () => {
      mockGet.mockResolvedValueOnce([]);

      await similarityService.findSimilar(1, 10, false);

      expect(mockGet).toHaveBeenCalledWith('/similarity/tracks/1/similar?limit=10&use_graph=false');
    });

    it('should propagate errors', async () => {
      mockGet.mockRejectedValueOnce(new Error('Network error'));

      await expect(similarityService.findSimilar(1)).rejects.toThrow('Network error');
    });
  });

  describe('compareTracks', () => {
    it('should compare two tracks', async () => {
      const mockResponse: ComparisonResult = {
        track_id1: 1,
        track_id2: 2,
        distance: 0.456,
        similarity_score: 0.72,
      };
      mockGet.mockResolvedValueOnce(mockResponse);

      const result = await similarityService.compareTracks(1, 2);

      expect(mockGet).toHaveBeenCalledWith('/similarity/tracks/1/compare/2');
      expect(result).toEqual(mockResponse);
      expect(result.distance).toBe(0.456);
    });

    it('should handle same track comparison', async () => {
      const mockResponse: ComparisonResult = {
        track_id1: 1,
        track_id2: 1,
        distance: 0.0,
        similarity_score: 1.0,
      };
      mockGet.mockResolvedValueOnce(mockResponse);

      const result = await similarityService.compareTracks(1, 1);

      expect(result.distance).toBe(0.0);
      expect(result.similarity_score).toBe(1.0);
    });

    it('should propagate errors', async () => {
      mockGet.mockRejectedValueOnce(new Error('Track not found'));

      await expect(similarityService.compareTracks(999999, 999998)).rejects.toThrow('Track not found');
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
          { dimension: 'bass_pct', contribution: 0.125, value1: 45.2, value2: 60.1, difference: 14.9 },
        ],
        all_contributions: [
          { dimension: 'bass_pct', contribution: 0.125, value1: 45.2, value2: 60.1, difference: 14.9 },
        ],
      };
      mockGet.mockResolvedValueOnce(mockResponse);

      const result = await similarityService.explainSimilarity(1, 2, 5);

      expect(mockGet).toHaveBeenCalledWith('/similarity/tracks/1/explain/2?top_n=5');
      expect(result).toEqual(mockResponse);
      expect(result.top_differences[0].dimension).toBe('bass_pct');
    });

    it('should use default topN parameter', async () => {
      mockGet.mockResolvedValueOnce({
        track_id1: 1, track_id2: 2, distance: 0.456, similarity_score: 0.72,
        top_differences: [], all_contributions: [],
      });

      await similarityService.explainSimilarity(1, 2);

      expect(mockGet).toHaveBeenCalledWith('/similarity/tracks/1/explain/2?top_n=5');
    });
  });

  describe('buildGraph', () => {
    it('should build K-NN graph with default k', async () => {
      mockPost.mockResolvedValueOnce(mockGraphStats);

      const result = await similarityService.buildGraph();

      expect(mockPost).toHaveBeenCalledWith('/similarity/graph/build?k=10', { k: 10 });
      expect(result).toEqual(mockGraphStats);
      expect(result.k_neighbors).toBe(10);
    });

    it('should build K-NN graph with custom k', async () => {
      const customStats = { ...mockGraphStats, total_edges: 500, k_neighbors: 5 };
      mockPost.mockResolvedValueOnce(customStats);

      await similarityService.buildGraph(5);

      expect(mockPost).toHaveBeenCalledWith('/similarity/graph/build?k=5', { k: 5 });
    });

    it('should propagate errors', async () => {
      mockPost.mockRejectedValueOnce(new Error('Insufficient fingerprints'));

      await expect(similarityService.buildGraph()).rejects.toThrow('Insufficient fingerprints');
    });
  });

  describe('getGraphStats', () => {
    it('should get graph statistics', async () => {
      mockGet.mockResolvedValueOnce(mockGraphStats);

      const result = await similarityService.getGraphStats();

      expect(mockGet).toHaveBeenCalledWith('/similarity/graph/stats');
      expect(result).toEqual(mockGraphStats);
    });

    it('should return null when graph does not exist (404)', async () => {
      mockGet.mockRejectedValueOnce(new APIRequestError('Not Found', 404));

      const result = await similarityService.getGraphStats();

      expect(result).toBeNull();
    });

    it('should propagate non-404 errors', async () => {
      mockGet.mockRejectedValueOnce(new APIRequestError('Server error', 500));

      await expect(similarityService.getGraphStats()).rejects.toThrow('Server error');
    });
  });

  describe('fit', () => {
    it('should fit similarity system with default parameters', async () => {
      const mockResponse: FitResult = { fitted: true, total_fingerprints: 50 };
      mockPost.mockResolvedValueOnce(mockResponse);

      const result = await similarityService.fit();

      expect(mockPost).toHaveBeenCalledWith('/similarity/fit?min_samples=10', { minSamples: 10 });
      expect(result.fitted).toBe(true);
    });

    it('should fit with custom min_samples', async () => {
      mockPost.mockResolvedValueOnce({ fitted: true, total_fingerprints: 100 });

      await similarityService.fit(20);

      expect(mockPost).toHaveBeenCalledWith('/similarity/fit?min_samples=20', { minSamples: 20 });
    });

    it('should handle insufficient fingerprints', async () => {
      const mockResponse: FitResult = { fitted: false, total_fingerprints: 5 };
      mockPost.mockResolvedValueOnce(mockResponse);

      const result = await similarityService.fit(10);

      expect(result.fitted).toBe(false);
    });
  });

  describe('isReady', () => {
    it('should return true when graph has edges', async () => {
      mockGet.mockResolvedValueOnce(mockGraphStats);

      const result = await similarityService.isReady();

      expect(result).toBe(true);
    });

    it('should return false when no graph exists (404)', async () => {
      mockGet.mockRejectedValueOnce(new APIRequestError('Not Found', 404));

      const result = await similarityService.isReady();

      expect(result).toBe(false);
    });

    it('should return false when graph has zero edges', async () => {
      mockGet.mockResolvedValueOnce({ ...mockGraphStats, total_edges: 0 });

      const result = await similarityService.isReady();

      expect(result).toBe(false);
    });

    it('should return false on network error', async () => {
      mockGet.mockRejectedValueOnce(new Error('Network error'));

      const result = await similarityService.isReady();

      expect(result).toBe(false);
    });
  });
});
