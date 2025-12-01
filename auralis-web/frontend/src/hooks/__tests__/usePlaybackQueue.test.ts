/**
 * usePlaybackQueue Hook Tests
 *
 * Comprehensive test suite for queue state management.
 * Covers: setQueue, addTrack, removeTrack, reorder, shuffle, repeat modes
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { usePlaybackQueue, usePlaybackQueueView } from '../player/usePlaybackQueue';
import * as useRestAPIModule from '../api/useRestAPI';
import * as useWebSocketModule from '../websocket/useWebSocketSubscription';

// Mock tracks for testing
const mockTracks = [
  {
    id: 1,
    title: 'Track 1',
    artist: 'Artist A',
    album: 'Album 1',
    duration: 180,
    filepath: '/music/track1.mp3',
  },
  {
    id: 2,
    title: 'Track 2',
    artist: 'Artist B',
    album: 'Album 2',
    duration: 240,
    filepath: '/music/track2.mp3',
  },
  {
    id: 3,
    title: 'Track 3',
    artist: 'Artist C',
    album: 'Album 3',
    duration: 200,
    filepath: '/music/track3.mp3',
  },
];

describe('usePlaybackQueue', () => {
  beforeEach(() => {
    // Mock useRestAPI
    vi.spyOn(useRestAPIModule, 'useRestAPI').mockReturnValue({
      get: vi.fn().mockResolvedValue({
        tracks: [],
        currentIndex: 0,
        isShuffled: false,
        repeatMode: 'off',
        lastUpdated: Date.now(),
      }),
      post: vi.fn().mockResolvedValue({}),
      put: vi.fn().mockResolvedValue({}),
      delete: vi.fn().mockResolvedValue({}),
      patch: vi.fn().mockResolvedValue({}),
      clearError: vi.fn(),
      isLoading: false,
      error: null,
    } as any);

    // Mock useWebSocketSubscription
    vi.spyOn(useWebSocketModule, 'useWebSocketSubscription').mockReturnValue(
      undefined as any
    );
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // =========================================================================
  // INITIALIZATION & STATE
  // =========================================================================

  it('should initialize with empty queue', () => {
    const { result } = renderHook(() => usePlaybackQueue());

    expect(result.current.queue).toEqual([]);
    expect(result.current.currentIndex).toBe(0);
    expect(result.current.currentTrack).toBeNull();
    expect(result.current.isShuffled).toBe(false);
    expect(result.current.repeatMode).toBe('off');
  });

  it('should fetch initial queue on mount', async () => {
    const mockGet = vi.fn().mockResolvedValue({
      tracks: mockTracks,
      currentIndex: 1,
      isShuffled: false,
      repeatMode: 'all',
      lastUpdated: Date.now(),
    });

    vi.spyOn(useRestAPIModule, 'useRestAPI').mockReturnValue({
      get: mockGet,
      post: vi.fn().mockResolvedValue({}),
      put: vi.fn().mockResolvedValue({}),
      delete: vi.fn().mockResolvedValue({}),
      patch: vi.fn().mockResolvedValue({}),
      clearError: vi.fn(),
      isLoading: false,
      error: null,
    } as any);

    const { result } = renderHook(() => usePlaybackQueue());

    await waitFor(() => {
      expect(result.current.queue).toEqual(mockTracks);
      expect(result.current.currentIndex).toBe(1);
      expect(result.current.repeatMode).toBe('all');
    });

    expect(mockGet).toHaveBeenCalledWith('/api/player/queue');
  });

  it('should get current track from queue', async () => {
    const mockGet = vi.fn().mockResolvedValue({
      tracks: mockTracks,
      currentIndex: 1,
      isShuffled: false,
      repeatMode: 'off',
      lastUpdated: Date.now(),
    });

    vi.spyOn(useRestAPIModule, 'useRestAPI').mockReturnValue({
      get: mockGet,
      post: vi.fn().mockResolvedValue({}),
      put: vi.fn().mockResolvedValue({}),
      delete: vi.fn().mockResolvedValue({}),
      patch: vi.fn().mockResolvedValue({}),
      clearError: vi.fn(),
      isLoading: false,
      error: null,
    } as any);

    const { result } = renderHook(() => usePlaybackQueue());

    await waitFor(() => {
      expect(result.current.currentTrack).toEqual(mockTracks[1]);
    });
  });

  // =========================================================================
  // SET QUEUE
  // =========================================================================

  it('should call setQueue API with correct parameters', async () => {
    const mockPost = vi.fn().mockResolvedValue({});

    vi.spyOn(useRestAPIModule, 'useRestAPI').mockReturnValue({
      get: vi.fn().mockResolvedValue({
        tracks: [],
        currentIndex: 0,
        isShuffled: false,
        repeatMode: 'off',
        lastUpdated: Date.now(),
      }),
      post: mockPost,
      put: vi.fn().mockResolvedValue({}),
      delete: vi.fn().mockResolvedValue({}),
      patch: vi.fn().mockResolvedValue({}),
      clearError: vi.fn(),
      isLoading: false,
      error: null,
    } as any);

    const { result } = renderHook(() => usePlaybackQueue());

    await act(async () => {
      await result.current.setQueue(mockTracks, 0);
    });

    expect(mockPost).toHaveBeenCalledWith('/api/player/queue', {
      tracks: [1, 2, 3],
      start_index: 0,
    });
  });

  it('should call setQueue API with custom start index', async () => {
    const mockPost = vi.fn().mockResolvedValue({});

    vi.spyOn(useRestAPIModule, 'useRestAPI').mockReturnValue({
      get: vi.fn().mockResolvedValue({
        tracks: [],
        currentIndex: 0,
        isShuffled: false,
        repeatMode: 'off',
        lastUpdated: Date.now(),
      }),
      post: mockPost,
      put: vi.fn().mockResolvedValue({}),
      delete: vi.fn().mockResolvedValue({}),
      patch: vi.fn().mockResolvedValue({}),
      clearError: vi.fn(),
      isLoading: false,
      error: null,
    } as any);

    const { result } = renderHook(() => usePlaybackQueue());

    await act(async () => {
      await result.current.setQueue(mockTracks, 2);
    });

    expect(mockPost).toHaveBeenCalledWith('/api/player/queue', {
      tracks: [1, 2, 3],
      start_index: 2,
    });
  });

  it('should handle setQueue errors', async () => {
    const mockError = new Error('Network error');
    const mockPost = vi.fn().mockRejectedValue(mockError);

    vi.spyOn(useRestAPIModule, 'useRestAPI').mockReturnValue({
      get: vi.fn().mockResolvedValue({
        tracks: [],
        currentIndex: 0,
        isShuffled: false,
        repeatMode: 'off',
        lastUpdated: Date.now(),
      }),
      post: mockPost,
      put: vi.fn().mockResolvedValue({}),
      delete: vi.fn().mockResolvedValue({}),
      patch: vi.fn().mockResolvedValue({}),
      clearError: vi.fn(),
      isLoading: false,
      error: null,
    } as any);

    const { result } = renderHook(() => usePlaybackQueue());

    await act(async () => {
      try {
        await result.current.setQueue(mockTracks);
      } catch (err) {
        expect(err).toBeDefined();
      }
    });

    expect(result.current.error).toBeDefined();
    expect(result.current.queue).toEqual([]); // Reverted
  });

  // =========================================================================
  // ADD TRACK
  // =========================================================================

  it('should add track to queue', async () => {
    const mockPost = vi.fn().mockResolvedValue({});

    vi.spyOn(useRestAPIModule, 'useRestAPI').mockReturnValue({
      get: vi.fn().mockResolvedValue({
        tracks: mockTracks.slice(0, 2),
        currentIndex: 0,
        isShuffled: false,
        repeatMode: 'off',
        lastUpdated: Date.now(),
      }),
      post: mockPost,
      put: vi.fn().mockResolvedValue({}),
      delete: vi.fn().mockResolvedValue({}),
      patch: vi.fn().mockResolvedValue({}),
      clearError: vi.fn(),
      isLoading: false,
      error: null,
    } as any);

    const { result } = renderHook(() => usePlaybackQueue());

    await waitFor(() => {
      expect(result.current.queue.length).toBe(2);
    });

    await act(async () => {
      await result.current.addTrack(mockTracks[2]);
    });

    expect(mockPost).toHaveBeenCalledWith('/api/player/queue/add', {
      track_id: 3,
      position: undefined,
    });
  });

  it('should add track at specific position', async () => {
    const mockPost = vi.fn().mockResolvedValue({});

    vi.spyOn(useRestAPIModule, 'useRestAPI').mockReturnValue({
      get: vi.fn().mockResolvedValue({
        tracks: mockTracks,
        currentIndex: 0,
        isShuffled: false,
        repeatMode: 'off',
        lastUpdated: Date.now(),
      }),
      post: mockPost,
      put: vi.fn().mockResolvedValue({}),
      delete: vi.fn().mockResolvedValue({}),
      patch: vi.fn().mockResolvedValue({}),
      clearError: vi.fn(),
      isLoading: false,
      error: null,
    } as any);

    const { result } = renderHook(() => usePlaybackQueue());

    await waitFor(() => {
      expect(result.current.queue.length).toBe(3);
    });

    const newTrack = {
      id: 4,
      title: 'Track 4',
      artist: 'Artist D',
      album: 'Album 4',
      duration: 220,
      filepath: '/music/track4.mp3',
    };

    await act(async () => {
      await result.current.addTrack(newTrack, 1);
    });

    expect(mockPost).toHaveBeenCalledWith('/api/player/queue/add', {
      track_id: 4,
      position: 1,
    });
  });

  // =========================================================================
  // REMOVE TRACK
  // =========================================================================

  it('should remove track from queue', async () => {
    const mockDelete = vi.fn().mockResolvedValue({});

    vi.spyOn(useRestAPIModule, 'useRestAPI').mockReturnValue({
      get: vi.fn().mockResolvedValue({
        tracks: mockTracks,
        currentIndex: 0,
        isShuffled: false,
        repeatMode: 'off',
        lastUpdated: Date.now(),
      }),
      post: vi.fn().mockResolvedValue({}),
      put: vi.fn().mockResolvedValue({}),
      delete: mockDelete,
      patch: vi.fn().mockResolvedValue({}),
      clearError: vi.fn(),
      isLoading: false,
      error: null,
    } as any);

    const { result } = renderHook(() => usePlaybackQueue());

    await waitFor(() => {
      expect(result.current.queue.length).toBe(3);
    });

    await act(async () => {
      await result.current.removeTrack(1);
    });

    expect(mockDelete).toHaveBeenCalledWith('/api/player/queue/1');
  });

  // =========================================================================
  // REORDER
  // =========================================================================

  it('should reorder single track in queue', async () => {
    const mockPut = vi.fn().mockResolvedValue({});

    vi.spyOn(useRestAPIModule, 'useRestAPI').mockReturnValue({
      get: vi.fn().mockResolvedValue({
        tracks: mockTracks,
        currentIndex: 0,
        isShuffled: false,
        repeatMode: 'off',
        lastUpdated: Date.now(),
      }),
      post: vi.fn().mockResolvedValue({}),
      put: mockPut,
      delete: vi.fn().mockResolvedValue({}),
      patch: vi.fn().mockResolvedValue({}),
      clearError: vi.fn(),
      isLoading: false,
      error: null,
    } as any);

    const { result } = renderHook(() => usePlaybackQueue());

    await waitFor(() => {
      expect(result.current.queue.length).toBe(3);
    });

    await act(async () => {
      await result.current.reorderTrack(0, 2);
    });

    expect(mockPut).toHaveBeenCalledWith('/api/player/queue/reorder', {
      from_index: 0,
      to_index: 2,
    });
  });

  it('should reorder entire queue by new order', async () => {
    const mockPut = vi.fn().mockResolvedValue({});

    vi.spyOn(useRestAPIModule, 'useRestAPI').mockReturnValue({
      get: vi.fn().mockResolvedValue({
        tracks: mockTracks,
        currentIndex: 0,
        isShuffled: false,
        repeatMode: 'off',
        lastUpdated: Date.now(),
      }),
      post: vi.fn().mockResolvedValue({}),
      put: mockPut,
      delete: vi.fn().mockResolvedValue({}),
      patch: vi.fn().mockResolvedValue({}),
      clearError: vi.fn(),
      isLoading: false,
      error: null,
    } as any);

    const { result } = renderHook(() => usePlaybackQueue());

    await waitFor(() => {
      expect(result.current.queue.length).toBe(3);
    });

    await act(async () => {
      await result.current.reorderQueue([3, 1, 2]);
    });

    expect(mockPut).toHaveBeenCalledWith('/api/player/queue/reorder', {
      new_order: [3, 1, 2],
    });
  });

  // =========================================================================
  // SHUFFLE
  // =========================================================================

  it('should toggle shuffle on', async () => {
    const mockPost = vi.fn().mockResolvedValue({});

    vi.spyOn(useRestAPIModule, 'useRestAPI').mockReturnValue({
      get: vi.fn().mockResolvedValue({
        tracks: mockTracks,
        currentIndex: 0,
        isShuffled: false,
        repeatMode: 'off',
        lastUpdated: Date.now(),
      }),
      post: mockPost,
      put: vi.fn().mockResolvedValue({}),
      delete: vi.fn().mockResolvedValue({}),
      patch: vi.fn().mockResolvedValue({}),
      clearError: vi.fn(),
      isLoading: false,
      error: null,
    } as any);

    const { result } = renderHook(() => usePlaybackQueue());

    await waitFor(() => {
      expect(result.current.isShuffled).toBe(false);
    });

    await act(async () => {
      await result.current.toggleShuffle();
    });

    expect(mockPost).toHaveBeenCalledWith('/api/player/queue/shuffle', undefined, {
      enabled: true,
    });

    expect(result.current.isShuffled).toBe(true);
  });

  it('should toggle shuffle off', async () => {
    const mockPost = vi.fn().mockResolvedValue({});

    vi.spyOn(useRestAPIModule, 'useRestAPI').mockReturnValue({
      get: vi.fn().mockResolvedValue({
        tracks: mockTracks,
        currentIndex: 0,
        isShuffled: true,
        repeatMode: 'off',
        lastUpdated: Date.now(),
      }),
      post: mockPost,
      put: vi.fn().mockResolvedValue({}),
      delete: vi.fn().mockResolvedValue({}),
      patch: vi.fn().mockResolvedValue({}),
      clearError: vi.fn(),
      isLoading: false,
      error: null,
    } as any);

    const { result } = renderHook(() => usePlaybackQueue());

    await waitFor(() => {
      expect(result.current.isShuffled).toBe(true);
    });

    await act(async () => {
      await result.current.toggleShuffle();
    });

    expect(mockPost).toHaveBeenCalledWith('/api/player/queue/shuffle', undefined, {
      enabled: false,
    });

    expect(result.current.isShuffled).toBe(false);
  });

  // =========================================================================
  // REPEAT MODE
  // =========================================================================

  it('should set repeat mode to all', async () => {
    const mockPost = vi.fn().mockResolvedValue({});

    vi.spyOn(useRestAPIModule, 'useRestAPI').mockReturnValue({
      get: vi.fn().mockResolvedValue({
        tracks: mockTracks,
        currentIndex: 0,
        isShuffled: false,
        repeatMode: 'off',
        lastUpdated: Date.now(),
      }),
      post: mockPost,
      put: vi.fn().mockResolvedValue({}),
      delete: vi.fn().mockResolvedValue({}),
      patch: vi.fn().mockResolvedValue({}),
      clearError: vi.fn(),
      isLoading: false,
      error: null,
    } as any);

    const { result } = renderHook(() => usePlaybackQueue());

    await waitFor(() => {
      expect(result.current.repeatMode).toBe('off');
    });

    await act(async () => {
      await result.current.setRepeatMode('all');
    });

    expect(mockPost).toHaveBeenCalledWith('/api/player/queue/repeat', undefined, {
      mode: 'all',
    });

    expect(result.current.repeatMode).toBe('all');
  });

  it('should set repeat mode to one', async () => {
    const mockPost = vi.fn().mockResolvedValue({});

    vi.spyOn(useRestAPIModule, 'useRestAPI').mockReturnValue({
      get: vi.fn().mockResolvedValue({
        tracks: mockTracks,
        currentIndex: 0,
        isShuffled: false,
        repeatMode: 'off',
        lastUpdated: Date.now(),
      }),
      post: mockPost,
      put: vi.fn().mockResolvedValue({}),
      delete: vi.fn().mockResolvedValue({}),
      patch: vi.fn().mockResolvedValue({}),
      clearError: vi.fn(),
      isLoading: false,
      error: null,
    } as any);

    const { result } = renderHook(() => usePlaybackQueue());

    await waitFor(() => {
      expect(result.current.repeatMode).toBe('off');
    });

    await act(async () => {
      await result.current.setRepeatMode('one');
    });

    await waitFor(() => {
      expect(result.current.repeatMode).toBe('one');
    });
  });

  it('should reject invalid repeat mode', async () => {
    const { result } = renderHook(() => usePlaybackQueue());

    await act(async () => {
      try {
        await result.current.setRepeatMode('invalid' as any);
      } catch (err) {
        expect(err).toBeDefined();
      }
    });

    expect(result.current.error).toBeDefined();
    expect(result.current.error?.code).toBe('INVALID_REPEAT_MODE');
  });

  // =========================================================================
  // CLEAR QUEUE
  // =========================================================================

  it('should clear entire queue', async () => {
    const mockPost = vi.fn().mockResolvedValue({});

    vi.spyOn(useRestAPIModule, 'useRestAPI').mockReturnValue({
      get: vi.fn().mockResolvedValue({
        tracks: mockTracks,
        currentIndex: 0,
        isShuffled: false,
        repeatMode: 'off',
        lastUpdated: Date.now(),
      }),
      post: mockPost,
      put: vi.fn().mockResolvedValue({}),
      delete: vi.fn().mockResolvedValue({}),
      patch: vi.fn().mockResolvedValue({}),
      clearError: vi.fn(),
      isLoading: false,
      error: null,
    } as any);

    const { result } = renderHook(() => usePlaybackQueue());

    await waitFor(() => {
      expect(result.current.queue.length).toBe(3);
    });

    await act(async () => {
      await result.current.clearQueue();
    });

    expect(mockPost).toHaveBeenCalledWith('/api/player/queue/clear');
    expect(result.current.queue).toEqual([]);
    expect(result.current.currentIndex).toBe(0);
  });

  // =========================================================================
  // ERROR HANDLING
  // =========================================================================

  it('should clear error state', async () => {
    const mockPost = vi.fn().mockRejectedValue(new Error('Test error'));

    vi.spyOn(useRestAPIModule, 'useRestAPI').mockReturnValue({
      get: vi.fn().mockResolvedValue({
        tracks: [],
        currentIndex: 0,
        isShuffled: false,
        repeatMode: 'off',
        lastUpdated: Date.now(),
      }),
      post: mockPost,
      put: vi.fn().mockResolvedValue({}),
      delete: vi.fn().mockResolvedValue({}),
      patch: vi.fn().mockResolvedValue({}),
      clearError: vi.fn(),
      isLoading: false,
      error: null,
    } as any);

    const { result } = renderHook(() => usePlaybackQueue());

    await act(async () => {
      try {
        await result.current.setQueue(mockTracks);
      } catch (err) {
        // Expected
      }
    });

    expect(result.current.error).toBeDefined();

    act(() => {
      result.current.clearError();
    });

    expect(result.current.error).toBeNull();
  });

  // =========================================================================
  // usePlaybackQueueView Convenience Hook
  // =========================================================================

  it('should provide view-only queue access', async () => {
    vi.spyOn(useRestAPIModule, 'useRestAPI').mockReturnValue({
      get: vi.fn().mockResolvedValue({
        tracks: mockTracks,
        currentIndex: 1,
        isShuffled: true,
        repeatMode: 'all',
        lastUpdated: Date.now(),
      }),
      post: vi.fn().mockResolvedValue({}),
      put: vi.fn().mockResolvedValue({}),
      delete: vi.fn().mockResolvedValue({}),
      patch: vi.fn().mockResolvedValue({}),
      clearError: vi.fn(),
      isLoading: false,
      error: null,
    } as any);

    const { result } = renderHook(() => usePlaybackQueueView());

    await waitFor(() => {
      expect(result.current.queue).toEqual(mockTracks);
      expect(result.current.currentIndex).toBe(1);
      expect(result.current.currentTrack).toEqual(mockTracks[1]);
      expect(result.current.isShuffled).toBe(true);
      expect(result.current.repeatMode).toBe('all');
    });
  });
});
