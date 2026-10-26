/**
 * Tests for Queue Service
 * ~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tests setQueue / addTrackToQueue, the calls with a production caller.
 * Mocks at the apiRequest module level to avoid MSW conflicts.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';

vi.mock('@/utils/apiRequest', () => ({
  post: vi.fn(),
  APIRequestError: class APIRequestError extends Error {
    constructor(message: string, public statusCode: number, public detail?: string) {
      super(message);
      this.name = 'APIRequestError';
    }
  },
}));

import { post } from '@/utils/apiRequest';
import { setQueue, addTrackToQueue } from '../queueService';

const mockPost = post as ReturnType<typeof vi.fn>;

describe('QueueService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('setQueue', () => {
    it('should set queue with default start index', async () => {
      const trackIds = [1, 2, 3];
      mockPost.mockResolvedValueOnce(undefined);

      await setQueue(trackIds);

      expect(mockPost).toHaveBeenCalledWith('/api/player/queue', {
        tracks: trackIds,
        start_index: 0,
      });
    });

    it('should set queue with custom start index', async () => {
      const trackIds = [1, 2, 3, 4, 5];
      mockPost.mockResolvedValueOnce(undefined);

      await setQueue(trackIds, 2);

      expect(mockPost).toHaveBeenCalledWith('/api/player/queue', {
        tracks: trackIds,
        start_index: 2,
      });
    });

    it('should set queue with single track', async () => {
      mockPost.mockResolvedValueOnce(undefined);

      await setQueue([42]);

      expect(mockPost).toHaveBeenCalledWith('/api/player/queue', {
        tracks: [42],
        start_index: 0,
      });
    });

    it('should set queue with many tracks', async () => {
      const manyTracks = Array.from({ length: 100 }, (_, i) => i + 1);
      mockPost.mockResolvedValueOnce(undefined);

      await setQueue(manyTracks, 50);

      const callArg = mockPost.mock.calls[0][1];
      expect(callArg.tracks).toHaveLength(100);
      expect(callArg.start_index).toBe(50);
    });

    it('should handle empty track array', async () => {
      mockPost.mockResolvedValueOnce(undefined);

      await setQueue([]);

      expect(mockPost).toHaveBeenCalledWith('/api/player/queue', {
        tracks: [],
        start_index: 0,
      });
    });

    it('should propagate errors', async () => {
      mockPost.mockRejectedValueOnce(new Error('Invalid track IDs'));

      await expect(setQueue([999, 1000])).rejects.toThrow('Invalid track IDs');
    });
  });

  describe('addTrackToQueue (#5612)', () => {
    it('posts the track id to the add-track endpoint', async () => {
      mockPost.mockResolvedValueOnce({});

      await addTrackToQueue(7);

      expect(mockPost).toHaveBeenCalledWith('/api/player/queue/add-track', { track_id: 7 });
    });

    it('includes the position only when one is given (0 is a real position)', async () => {
      mockPost.mockResolvedValue({});

      await addTrackToQueue(7, 0);
      await addTrackToQueue(8, 3);

      expect(mockPost).toHaveBeenNthCalledWith(1, '/api/player/queue/add-track', { track_id: 7, position: 0 });
      expect(mockPost).toHaveBeenNthCalledWith(2, '/api/player/queue/add-track', { track_id: 8, position: 3 });
    });

    it('propagates errors so callers do not show a false success', async () => {
      mockPost.mockRejectedValueOnce(new Error('Track 99 not found'));

      await expect(addTrackToQueue(99)).rejects.toThrow('Track 99 not found');
    });
  });
});
