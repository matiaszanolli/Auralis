/**
 * useSimilarTracksLoader Hook Tests
 *
 * Tests for loading similar tracks:
 * - Fetching similar tracks via API
 * - Loading state management
 * - Error handling
 */

import { vi } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useSimilarTracksLoader } from '../useSimilarTracksLoader';
import similarityService from '../services/similarityService';

// Mock the similarity service
vi.mock('../services/similarityService', () => ({
  default: {
    findSimilar: vi.fn(),
  },
}));

const mockSimilarTracks = [
  { track_id: 2, title: 'Similar Track 1', artist: 'Artist A', similarity_score: 0.95 },
  { track_id: 3, title: 'Similar Track 2', artist: 'Artist B', similarity_score: 0.87 },
  { track_id: 4, title: 'Similar Track 3', artist: 'Artist C', similarity_score: 0.75 },
];

describe('useSimilarTracksLoader', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(similarityService.findSimilar).mockResolvedValue(mockSimilarTracks);
  });

  describe('Hook Initialization', () => {
    it('should initialize with empty tracks and false loading', () => {
      const { result } = renderHook(() =>
        useSimilarTracksLoader({
          trackId: null,
          limit: 10,
          useGraph: false,
        })
      );

      expect(result.current.similarTracks).toEqual([]);
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBeNull();
    });
  });

  describe('Fetching Similar Tracks', () => {
    it('should fetch similar tracks when trackId changes', async () => {
      const { result } = renderHook(() =>
        useSimilarTracksLoader({
          trackId: 1,
          limit: 10,
          useGraph: false,
        })
      );

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(similarityService.findSimilar).toHaveBeenCalledWith(1, 10, false);
      expect(result.current.similarTracks).toEqual(mockSimilarTracks);
    });

    it('should set loading state during fetch', async () => {
      const { result } = renderHook(() =>
        useSimilarTracksLoader({
          trackId: 1,
          limit: 10,
          useGraph: false,
        })
      );

      // Loading should eventually be false after fetch completes
      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(similarityService.findSimilar).toHaveBeenCalled();
    });

    it('should handle successful track loading', async () => {
      const { result } = renderHook(() =>
        useSimilarTracksLoader({
          trackId: 1,
          limit: 10,
          useGraph: false,
        })
      );

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.similarTracks).toEqual(mockSimilarTracks);
      expect(result.current.error).toBeNull();
    });
  });

  describe('Error Handling', () => {
    it('should handle API errors gracefully', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      const errorMessage = 'Network error';
      vi.mocked(similarityService.findSimilar).mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() =>
        useSimilarTracksLoader({
          trackId: 1,
          limit: 10,
          useGraph: false,
        })
      );

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.error).toBe(errorMessage);
      expect(result.current.similarTracks).toEqual([]);

      consoleErrorSpy.mockRestore();
    });

    it('should reset tracks on error', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      const { result, rerender } = renderHook(
        ({ trackId }) =>
          useSimilarTracksLoader({
            trackId,
            limit: 10,
            useGraph: false,
          }),
        {
          initialProps: { trackId: 1 },
        }
      );

      // First load success
      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.similarTracks).toEqual(mockSimilarTracks);

      // Now mock error for next fetch
      vi.mocked(similarityService.findSimilar).mockRejectedValue(new Error('API Error'));

      // Change trackId to trigger new fetch
      rerender({ trackId: 2 });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.similarTracks).toEqual([]);
      expect(result.current.error).toBe('API Error');

      consoleErrorSpy.mockRestore();
    });
  });

  describe('Parameter Handling', () => {
    it('should respect limit parameter', async () => {
      const { result } = renderHook(() =>
        useSimilarTracksLoader({
          trackId: 1,
          limit: 5,
          useGraph: false,
        })
      );

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(similarityService.findSimilar).toHaveBeenCalledWith(1, 5, false);
    });

    it('should use graph mode when specified', async () => {
      const { result } = renderHook(() =>
        useSimilarTracksLoader({
          trackId: 1,
          limit: 10,
          useGraph: true,
        })
      );

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(similarityService.findSimilar).toHaveBeenCalledWith(1, 10, true);
    });

    it('should skip fetch when trackId is null', async () => {
      const { result } = renderHook(() =>
        useSimilarTracksLoader({
          trackId: null,
          limit: 10,
          useGraph: false,
        })
      );

      // Give it a moment to see if fetch would be called
      await new Promise((resolve) => setTimeout(resolve, 50));

      expect(similarityService.findSimilar).not.toHaveBeenCalled();
      expect(result.current.similarTracks).toEqual([]);
    });

    it('should clear tracks when trackId becomes null', async () => {
      const { result, rerender } = renderHook(
        ({ trackId }) =>
          useSimilarTracksLoader({
            trackId,
            limit: 10,
            useGraph: false,
          }),
        {
          initialProps: { trackId: 1 },
        }
      );

      // First load with trackId
      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.similarTracks).toEqual(mockSimilarTracks);

      // Clear trackId
      rerender({ trackId: null });

      await waitFor(() => {
        expect(result.current.similarTracks).toEqual([]);
      });
    });
  });

  describe('Dependency Array', () => {
    it('should re-fetch when trackId changes', async () => {
      const { result, rerender } = renderHook(
        ({ trackId }) =>
          useSimilarTracksLoader({
            trackId,
            limit: 10,
            useGraph: false,
          }),
        {
          initialProps: { trackId: 1 },
        }
      );

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(similarityService.findSimilar).toHaveBeenCalledTimes(1);
      expect(similarityService.findSimilar).toHaveBeenCalledWith(1, 10, false);

      // Change trackId
      rerender({ trackId: 2 });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(similarityService.findSimilar).toHaveBeenCalledTimes(2);
      expect(similarityService.findSimilar).toHaveBeenCalledWith(2, 10, false);
    });

    it('should re-fetch when limit changes', async () => {
      const { result, rerender } = renderHook(
        ({ trackId, limit }) =>
          useSimilarTracksLoader({
            trackId,
            limit,
            useGraph: false,
          }),
        {
          initialProps: { trackId: 1, limit: 10 },
        }
      );

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(similarityService.findSimilar).toHaveBeenCalledWith(1, 10, false);

      // Change limit
      rerender({ trackId: 1, limit: 20 });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(similarityService.findSimilar).toHaveBeenCalledWith(1, 20, false);
    });

    it('should re-fetch when useGraph changes', async () => {
      const { result, rerender } = renderHook(
        ({ trackId, useGraph }) =>
          useSimilarTracksLoader({
            trackId,
            limit: 10,
            useGraph,
          }),
        {
          initialProps: { trackId: 1, useGraph: false },
        }
      );

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(similarityService.findSimilar).toHaveBeenCalledWith(1, 10, false);

      // Change useGraph
      rerender({ trackId: 1, useGraph: true });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(similarityService.findSimilar).toHaveBeenCalledWith(1, 10, true);
    });
  });

  describe('Handler Memoization', () => {
    it('should memoize loadSimilarTracks callback', async () => {
      const { result, rerender } = renderHook(
        ({ trackId }) =>
          useSimilarTracksLoader({
            trackId,
            limit: 10,
            useGraph: false,
          }),
        {
          initialProps: { trackId: 1 },
        }
      );

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      // Rerender with same props
      rerender({ trackId: 1 });

      // Callback should remain memoized when props don't change
      expect(similarityService.findSimilar).toHaveBeenCalledTimes(1);
    });
  });
});
