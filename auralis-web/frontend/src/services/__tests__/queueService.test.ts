/**
 * Tests for Queue Service
 * ~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tests the playback queue management service
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  getQueue,
  removeTrackFromQueue,
  reorderQueue,
  shuffleQueue,
  clearQueue,
  setQueue,
  type QueueResponse,
  type QueueTrack,
} from '../queueService';

// Mock fetch
global.fetch = vi.fn();

const mockQueueTracks: QueueTrack[] = [
  {
    id: 1,
    title: 'Track 1',
    artist: 'Artist 1',
    album: 'Album 1',
    duration: 180,
    filepath: '/music/track1.mp3',
  },
  {
    id: 2,
    title: 'Track 2',
    artist: 'Artist 2',
    album: 'Album 2',
    duration: 240,
    filepath: '/music/track2.mp3',
  },
  {
    id: 3,
    title: 'Track 3',
    duration: 200,
    filepath: '/music/track3.mp3',
  },
];

const mockQueueResponse: QueueResponse = {
  tracks: mockQueueTracks,
  current_index: 0,
  total_tracks: 3,
};

describe('QueueService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getQueue', () => {
    it('should get current queue successfully', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockQueueResponse,
      });

      const result = await getQueue();

      expect(global.fetch).toHaveBeenCalledWith('/api/player/queue');
      expect(result).toEqual(mockQueueResponse);
      expect(result.tracks).toHaveLength(3);
      expect(result.current_index).toBe(0);
      expect(result.total_tracks).toBe(3);
    });

    it('should get empty queue', async () => {
      const emptyQueue: QueueResponse = {
        tracks: [],
        current_index: -1,
        total_tracks: 0,
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => emptyQueue,
      });

      const result = await getQueue();

      expect(result.tracks).toHaveLength(0);
      expect(result.total_tracks).toBe(0);
    });

    it('should throw error on failed fetch', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        statusText: 'Server Error',
      });

      await expect(getQueue()).rejects.toThrow('Failed to get queue: Server Error');
    });

    it('should handle network errors', async () => {
      (global.fetch as any).mockRejectedValueOnce(new Error('Network error'));

      await expect(getQueue()).rejects.toThrow('Network error');
    });

    it('should return tracks with all fields', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockQueueResponse,
      });

      const result = await getQueue();

      const track = result.tracks[0];
      expect(track).toHaveProperty('id');
      expect(track).toHaveProperty('title');
      expect(track).toHaveProperty('duration');
      expect(track).toHaveProperty('filepath');
    });

    it('should handle tracks without optional fields', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockQueueResponse,
      });

      const result = await getQueue();

      const trackWithoutOptional = result.tracks[2];
      expect(trackWithoutOptional.artist).toBeUndefined();
      expect(trackWithoutOptional.album).toBeUndefined();
    });
  });

  describe('removeTrackFromQueue', () => {
    it('should remove track at index 0', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await removeTrackFromQueue(0);

      expect(global.fetch).toHaveBeenCalledWith('/api/player/queue/0', {
        method: 'DELETE',
      });
    });

    it('should remove track at various indices', async () => {
      for (const index of [0, 1, 2, 5, 10]) {
        (global.fetch as any).mockResolvedValueOnce({
          ok: true,
          json: async () => ({}),
        });

        await removeTrackFromQueue(index);

        expect(global.fetch).toHaveBeenCalledWith(
          `/api/player/queue/${index}`,
          { method: 'DELETE' }
        );
      }
    });

    it('should throw error with detail message', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: 'Index out of range' }),
      });

      await expect(removeTrackFromQueue(999)).rejects.toThrow('Index out of range');
    });

    it('should throw generic error when no detail', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        json: async () => ({}),
      });

      await expect(removeTrackFromQueue(0)).rejects.toThrow('Failed to remove track from queue');
    });

    it('should handle negative indices', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: 'Invalid index' }),
      });

      await expect(removeTrackFromQueue(-1)).rejects.toThrow('Invalid index');
    });

    it('should handle network errors', async () => {
      (global.fetch as any).mockRejectedValueOnce(new Error('Connection lost'));

      await expect(removeTrackFromQueue(0)).rejects.toThrow('Connection lost');
    });
  });

  describe('reorderQueue', () => {
    it('should reorder queue successfully', async () => {
      const newOrder = [2, 0, 1];

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await reorderQueue(newOrder);

      expect(global.fetch).toHaveBeenCalledWith('/api/player/queue/reorder', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ new_order: newOrder }),
      });
    });

    it('should reorder with different patterns', async () => {
      const patterns = [
        [0, 1, 2],        // No change
        [2, 1, 0],        // Reverse
        [1, 0, 2],        // Swap first two
        [0, 2, 1, 3, 4],  // Complex reorder
      ];

      for (const newOrder of patterns) {
        (global.fetch as any).mockResolvedValueOnce({
          ok: true,
          json: async () => ({}),
        });

        await reorderQueue(newOrder);

        const call = (global.fetch as any).mock.calls[0];
        const body = JSON.parse(call[1].body);
        expect(body.new_order).toEqual(newOrder);

        vi.clearAllMocks();
      }
    });

    it('should throw error with detail message', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: 'Invalid reorder pattern' }),
      });

      await expect(reorderQueue([0, 1, 999])).rejects.toThrow('Invalid reorder pattern');
    });

    it('should throw generic error when no detail', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        json: async () => ({}),
      });

      await expect(reorderQueue([0, 1])).rejects.toThrow('Failed to reorder queue');
    });

    it('should handle empty array', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await reorderQueue([]);

      const call = (global.fetch as any).mock.calls[0];
      const body = JSON.parse(call[1].body);
      expect(body.new_order).toEqual([]);
    });

    it('should handle large arrays', async () => {
      const largeArray = Array.from({ length: 1000 }, (_, i) => i);

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await reorderQueue(largeArray);

      const call = (global.fetch as any).mock.calls[0];
      const body = JSON.parse(call[1].body);
      expect(body.new_order).toHaveLength(1000);
    });
  });

  describe('shuffleQueue', () => {
    it('should shuffle queue successfully', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await shuffleQueue();

      expect(global.fetch).toHaveBeenCalledWith('/api/player/queue/shuffle', {
        method: 'POST',
      });
    });

    it('should throw error with detail message', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: 'Queue is empty' }),
      });

      await expect(shuffleQueue()).rejects.toThrow('Queue is empty');
    });

    it('should throw generic error when no detail', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        json: async () => ({}),
      });

      await expect(shuffleQueue()).rejects.toThrow('Failed to shuffle queue');
    });

    it('should handle network errors', async () => {
      (global.fetch as any).mockRejectedValueOnce(new Error('Timeout'));

      await expect(shuffleQueue()).rejects.toThrow('Timeout');
    });

    it('should not send any body data', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await shuffleQueue();

      const call = (global.fetch as any).mock.calls[0];
      expect(call[1].body).toBeUndefined();
    });
  });

  describe('clearQueue', () => {
    it('should clear queue successfully', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await clearQueue();

      expect(global.fetch).toHaveBeenCalledWith('/api/player/queue/clear', {
        method: 'POST',
      });
    });

    it('should throw error with detail message', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: 'Permission denied' }),
      });

      await expect(clearQueue()).rejects.toThrow('Permission denied');
    });

    it('should throw generic error when no detail', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        json: async () => ({}),
      });

      await expect(clearQueue()).rejects.toThrow('Failed to clear queue');
    });

    it('should handle network errors', async () => {
      (global.fetch as any).mockRejectedValueOnce(new Error('Server unavailable'));

      await expect(clearQueue()).rejects.toThrow('Server unavailable');
    });

    it('should not send any body data', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await clearQueue();

      const call = (global.fetch as any).mock.calls[0];
      expect(call[1].body).toBeUndefined();
    });
  });

  describe('setQueue', () => {
    it('should set queue with default start index', async () => {
      const trackIds = [1, 2, 3];

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await setQueue(trackIds);

      expect(global.fetch).toHaveBeenCalledWith('/api/player/queue', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          tracks: trackIds,
          start_index: 0,
        }),
      });
    });

    it('should set queue with custom start index', async () => {
      const trackIds = [1, 2, 3, 4, 5];
      const startIndex = 2;

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await setQueue(trackIds, startIndex);

      const call = (global.fetch as any).mock.calls[0];
      const body = JSON.parse(call[1].body);
      expect(body.tracks).toEqual(trackIds);
      expect(body.start_index).toBe(2);
    });

    it('should set queue with various start indices', async () => {
      const trackIds = [10, 20, 30, 40, 50];

      for (const startIndex of [0, 1, 2, 3, 4]) {
        (global.fetch as any).mockResolvedValueOnce({
          ok: true,
          json: async () => ({}),
        });

        await setQueue(trackIds, startIndex);

        const call = (global.fetch as any).mock.calls[0];
        const body = JSON.parse(call[1].body);
        expect(body.start_index).toBe(startIndex);

        vi.clearAllMocks();
      }
    });

    it('should set queue with single track', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await setQueue([42]);

      const call = (global.fetch as any).mock.calls[0];
      const body = JSON.parse(call[1].body);
      expect(body.tracks).toEqual([42]);
      expect(body.start_index).toBe(0);
    });

    it('should set queue with many tracks', async () => {
      const manyTracks = Array.from({ length: 100 }, (_, i) => i + 1);

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await setQueue(manyTracks, 50);

      const call = (global.fetch as any).mock.calls[0];
      const body = JSON.parse(call[1].body);
      expect(body.tracks).toHaveLength(100);
      expect(body.start_index).toBe(50);
    });

    it('should throw error with detail message', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: 'Invalid track IDs' }),
      });

      await expect(setQueue([999, 1000])).rejects.toThrow('Invalid track IDs');
    });

    it('should throw generic error when no detail', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        json: async () => ({}),
      });

      await expect(setQueue([1, 2])).rejects.toThrow('Failed to set queue');
    });

    it('should handle empty track array', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await setQueue([]);

      const call = (global.fetch as any).mock.calls[0];
      const body = JSON.parse(call[1].body);
      expect(body.tracks).toEqual([]);
    });

    it('should handle network errors', async () => {
      (global.fetch as any).mockRejectedValueOnce(new Error('Connection failed'));

      await expect(setQueue([1, 2, 3])).rejects.toThrow('Connection failed');
    });
  });

  describe('Integration scenarios', () => {
    it('should handle complete queue workflow', async () => {
      // Set queue
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });
      await setQueue([1, 2, 3], 0);

      // Get queue
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockQueueResponse,
      });
      const queue = await getQueue();
      expect(queue.tracks).toHaveLength(3);

      // Remove track
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });
      await removeTrackFromQueue(1);

      // Shuffle
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });
      await shuffleQueue();

      // Clear
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });
      await clearQueue();
    });

    it('should handle reorder then shuffle workflow', async () => {
      // Reorder
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });
      await reorderQueue([2, 0, 1]);

      // Shuffle
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });
      await shuffleQueue();

      expect(global.fetch).toHaveBeenCalledTimes(2);
    });

    it('should handle multiple concurrent operations', async () => {
      const operations = [
        shuffleQueue,
        () => setQueue([1, 2, 3]),
        () => removeTrackFromQueue(0),
      ];

      const promises = operations.map(op => {
        (global.fetch as any).mockResolvedValueOnce({
          ok: true,
          json: async () => ({}),
        });
        return op();
      });

      await Promise.all(promises);

      expect(global.fetch).toHaveBeenCalledTimes(3);
    });
  });

  describe('Error handling edge cases', () => {
    it('should handle malformed JSON response', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => { throw new Error('Invalid JSON'); },
      });

      await expect(getQueue()).rejects.toThrow();
    });

    it('should handle null response', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => null,
      });

      const result = await getQueue();
      expect(result).toBeNull();
    });

    it('should handle 404 errors', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: 'Not Found',
      });

      await expect(getQueue()).rejects.toThrow('Failed to get queue: Not Found');
    });

    it('should handle 500 errors', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ detail: 'Internal server error' }),
      });

      await expect(removeTrackFromQueue(0)).rejects.toThrow('Internal server error');
    });

    it('should handle timeout in setQueue', async () => {
      (global.fetch as any).mockImplementationOnce(() =>
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error('Request timeout')), 100)
        )
      );

      await expect(setQueue([1, 2, 3])).rejects.toThrow('Request timeout');
    });
  });
});
