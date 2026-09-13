/**
 * Tests for Queue Service
 * ~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tests the playback queue management service.
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

import { get, post, put, del } from '@/utils/apiRequest';
import {
  getQueue,
  removeTrackFromQueue,
  reorderQueue,
  shuffleQueue,
  clearQueue,
  setQueue,
  type QueueResponse,
} from '../queueService';
import type { TrackInfo } from '@/types/websocket';

const mockGet = get as ReturnType<typeof vi.fn>;
const mockPost = post as ReturnType<typeof vi.fn>;
const mockPut = put as ReturnType<typeof vi.fn>;
const mockDel = del as ReturnType<typeof vi.fn>;

// #5018: artist/album are always present on the wire (player_state.py's
// TrackInfo); filepath is never actually sent (Field(exclude=True)) but is
// kept here as optional test data, matching TrackInfo's own shape.
const mockQueueTracks: TrackInfo[] = [
  { id: 1, title: 'Track 1', artist: 'Artist 1', album: 'Album 1', duration: 180 },
  { id: 2, title: 'Track 2', artist: 'Artist 2', album: 'Album 2', duration: 240 },
  { id: 3, title: 'Track 3', artist: 'Artist 3', album: 'Album 3', duration: 200 },
];

const mockQueueResponse: QueueResponse = {
  tracks: mockQueueTracks,
  current_index: 0,
  track_count: 3,
};

describe('QueueService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getQueue', () => {
    it('should get current queue successfully', async () => {
      // GET /api/player/queue returns a single QueueInfoResponse object, NOT an
      // array — mock the real wire shape so a regression to the array-only path
      // (which discarded the response for an empty default) is caught (#4441).
      mockGet.mockResolvedValueOnce(mockQueueResponse);

      const result = await getQueue();

      // #4607: the queue endpoint now carries a runtime shape guard — the exact
      // drift class that made #4441 silently return an empty queue.
      expect(mockGet).toHaveBeenCalledWith('/api/player/queue', {
        validate: expect.any(Function),
      });
      expect(result).toEqual(mockQueueResponse);
      expect(result.tracks).toHaveLength(3);
    });

    it('should return empty queue when server returns empty array', async () => {
      mockGet.mockResolvedValueOnce([]);

      const result = await getQueue();

      expect(result).toEqual({ tracks: [], current_index: 0, track_count: 0 });
    });

    it('should return tracks with all fields', async () => {
      mockGet.mockResolvedValueOnce(mockQueueResponse);

      const result = await getQueue();
      const track = result.tracks[0];

      expect(track).toHaveProperty('id');
      expect(track).toHaveProperty('title');
      expect(track).toHaveProperty('duration');
      // #5018: artist/album are always present on the real wire contract
      // (player_state.py's TrackInfo) — the corrected type reflects that.
      expect(track).toHaveProperty('artist');
      expect(track).toHaveProperty('album');
    });

    it('should handle tracks without filepath (the real, always-true case)', async () => {
      // #5018: filepath is genuinely optional/never sent (Field(exclude=True)
      // on the backend) — the corrected type/contract this test now covers,
      // replacing a prior test that (incorrectly) treated artist/album as
      // the optional fields instead.
      mockGet.mockResolvedValueOnce(mockQueueResponse);

      const result = await getQueue();

      expect(result.tracks[0].filepath).toBeUndefined();
    });

    it('should propagate errors', async () => {
      mockGet.mockRejectedValueOnce(new Error('Network error'));

      await expect(getQueue()).rejects.toThrow('Network error');
    });
  });

  describe('removeTrackFromQueue', () => {
    it('should remove track at index 0', async () => {
      mockDel.mockResolvedValueOnce(undefined);

      await removeTrackFromQueue(0);

      expect(mockDel).toHaveBeenCalledWith('/api/player/queue/0');
    });

    it('should remove track at various indices', async () => {
      for (const index of [0, 1, 2, 5, 10]) {
        mockDel.mockResolvedValueOnce(undefined);
        await removeTrackFromQueue(index);
        expect(mockDel).toHaveBeenCalledWith(`/api/player/queue/${index}`);
        vi.clearAllMocks();
      }
    });

    it('should propagate errors', async () => {
      mockDel.mockRejectedValueOnce(new Error('Index out of range'));

      await expect(removeTrackFromQueue(999)).rejects.toThrow('Index out of range');
    });
  });

  describe('reorderQueue', () => {
    it('should reorder queue with correct payload', async () => {
      const newOrder = [2, 0, 1];
      mockPut.mockResolvedValueOnce(undefined);

      await reorderQueue(newOrder);

      expect(mockPut).toHaveBeenCalledWith('/api/player/queue/reorder', { new_order: newOrder });
    });

    it('should handle empty array', async () => {
      mockPut.mockResolvedValueOnce(undefined);

      await reorderQueue([]);

      expect(mockPut).toHaveBeenCalledWith('/api/player/queue/reorder', { new_order: [] });
    });

    it('should handle large arrays', async () => {
      const largeArray = Array.from({ length: 1000 }, (_, i) => i);
      mockPut.mockResolvedValueOnce(undefined);

      await reorderQueue(largeArray);

      const callArg = mockPut.mock.calls[0][1];
      expect(callArg.new_order).toHaveLength(1000);
    });

    it('should propagate errors', async () => {
      mockPut.mockRejectedValueOnce(new Error('Invalid reorder pattern'));

      await expect(reorderQueue([0, 1, 999])).rejects.toThrow('Invalid reorder pattern');
    });
  });

  describe('shuffleQueue', () => {
    it('should shuffle queue successfully', async () => {
      mockPost.mockResolvedValueOnce(undefined);

      await shuffleQueue();

      expect(mockPost).toHaveBeenCalledWith('/api/player/queue/shuffle', {});
    });

    it('should propagate errors', async () => {
      mockPost.mockRejectedValueOnce(new Error('Queue is empty'));

      await expect(shuffleQueue()).rejects.toThrow('Queue is empty');
    });
  });

  describe('clearQueue', () => {
    it('should clear queue successfully', async () => {
      mockPost.mockResolvedValueOnce(undefined);

      await clearQueue();

      expect(mockPost).toHaveBeenCalledWith('/api/player/queue/clear', {});
    });

    it('should propagate errors', async () => {
      mockPost.mockRejectedValueOnce(new Error('Permission denied'));

      await expect(clearQueue()).rejects.toThrow('Permission denied');
    });
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
});
