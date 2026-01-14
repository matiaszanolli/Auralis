/**
 * useTrackContextMenu Hook Tests
 *
 * Tests for track context menu state and actions:
 * - Context menu position management
 * - Playlist fetching and operations
 * - Context actions generation
 */

import React from 'react';
import { vi } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { useTrackContextMenu } from '../tracks/useTrackContextMenu';
import playerReducer from '@/store/slices/playerSlice';
import queueReducer from '@/store/slices/queueSlice';

// Create mock toast functions that can be controlled per-test
const mockToastSuccess = vi.fn();
const mockToastInfo = vi.fn();
const mockToastError = vi.fn();
const mockToastWarning = vi.fn();

// Create stable toast object for referential equality
const mockToastObject = {
  success: mockToastSuccess,
  info: mockToastInfo,
  error: mockToastError,
  warning: mockToastWarning,
};

// Create stable context actions array for referential equality
const mockContextActions: any[] = [];

// Mock dependencies
vi.mock('@/components/shared/Toast', () => ({
  useToast: vi.fn(() => mockToastObject),
}));

vi.mock('@/services/playlistService', () => ({
  getPlaylists: vi.fn(),
  addTracksToPlaylist: vi.fn(),
  createPlaylist: vi.fn(),
}));

vi.mock('@/components/shared/ContextMenu', () => ({
  getTrackContextActions: vi.fn(() => mockContextActions),
}));

import * as playlistService from '@/services/playlistService';
import { useToast } from '@/components/shared/Toast';

// Create a test store
const createTestStore = () => {
  return configureStore({
    reducer: {
      player: playerReducer,
      queue: queueReducer,
    },
  });
};

// Wrapper component that provides Redux store
const createWrapper = () => {
  const store = createTestStore();
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(Provider, { store }, children);
  };
};

const mockTrack = {
  id: 1,
  title: 'Test Track',
  artist: 'Test Artist',
  album: 'Test Album',
  duration: 180,
  album_id: 1,
  favorite: false,
};

const mockPlaylists = [
  { id: 1, name: 'Favorites', trackCount: 10 },
  { id: 2, name: 'Workout', trackCount: 25 },
];

describe('useTrackContextMenu', () => {
  const mockOnPlay = vi.fn();
  const mockOnToggleFavorite = vi.fn();
  const mockOnShowAlbum = vi.fn();
  const mockOnShowArtist = vi.fn();
  const mockOnShowInfo = vi.fn();
  const mockOnEditMetadata = vi.fn();
  const mockOnDelete = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(playlistService.getPlaylists).mockResolvedValue({
      playlists: mockPlaylists,
    });
  });

  describe('Hook Initialization', () => {
    it('should initialize with null context menu position', () => {
      const { result } = renderHook(() =>
        useTrackContextMenu({
          track: mockTrack,
          onPlay: mockOnPlay,
        }),
        { wrapper: createWrapper() }
      );

      expect(result.current.contextMenuPosition).toBeNull();
      expect(result.current.playlists).toEqual([]);
      expect(result.current.isLoadingPlaylists).toBe(false);
    });
  });

  describe('handleMoreClick', () => {
    it('should set context menu position', async () => {
      const { result } = renderHook(() =>
        useTrackContextMenu({
          track: mockTrack,
          onPlay: mockOnPlay,
        }),
        { wrapper: createWrapper() }
      );

      const mockEvent = {
        clientX: 100,
        clientY: 50,
        stopPropagation: vi.fn(),
      } as unknown as React.MouseEvent;

      await act(async () => {
        result.current.handleMoreClick(mockEvent);
      });

      expect(result.current.contextMenuPosition).toEqual({
        left: 100,
        top: 50,
      });
      expect(mockEvent.stopPropagation).toHaveBeenCalled();
    });
  });

  describe('handleTrackContextMenu', () => {
    it('should prevent default and set position', async () => {
      const { result } = renderHook(() =>
        useTrackContextMenu({
          track: mockTrack,
          onPlay: mockOnPlay,
        }),
        { wrapper: createWrapper() }
      );

      const mockEvent = {
        clientX: 200,
        clientY: 150,
        preventDefault: vi.fn(),
        stopPropagation: vi.fn(),
      } as unknown as React.MouseEvent;

      await act(async () => {
        result.current.handleTrackContextMenu(mockEvent);
      });

      expect(mockEvent.preventDefault).toHaveBeenCalled();
      expect(mockEvent.stopPropagation).toHaveBeenCalled();
      expect(result.current.contextMenuPosition).toEqual({
        left: 200,
        top: 150,
      });
    });
  });

  describe('handleCloseContextMenu', () => {
    it('should reset context menu position', async () => {
      const { result } = renderHook(() =>
        useTrackContextMenu({
          track: mockTrack,
          onPlay: mockOnPlay,
        }),
        { wrapper: createWrapper() }
      );

      const mockEvent = {
        clientX: 100,
        clientY: 50,
        stopPropagation: vi.fn(),
      } as unknown as React.MouseEvent;

      // First open the menu
      await act(async () => {
        result.current.handleMoreClick(mockEvent);
      });

      expect(result.current.contextMenuPosition).not.toBeNull();

      // Then close it
      await act(async () => {
        result.current.handleCloseContextMenu();
      });

      expect(result.current.contextMenuPosition).toBeNull();
    });
  });

  describe('Playlist Loading', () => {
    it('should fetch playlists on demand', async () => {
      const { result } = renderHook(() =>
        useTrackContextMenu({
          track: mockTrack,
          onPlay: mockOnPlay,
        }),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        await result.current.fetchPlaylists();
      });

      expect(playlistService.getPlaylists).toHaveBeenCalled();
      expect(result.current.playlists).toEqual(mockPlaylists);
    });

    it('should handle fetch errors gracefully', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      vi.mocked(playlistService.getPlaylists).mockRejectedValue(
        new Error('Network error')
      );

      const { result } = renderHook(() =>
        useTrackContextMenu({
          track: mockTrack,
          onPlay: mockOnPlay,
        }),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        await result.current.fetchPlaylists();
      });

      expect(result.current.playlists).toEqual([]);
      expect(result.current.isLoadingPlaylists).toBe(false);

      consoleErrorSpy.mockRestore();
    });

    it('should set loading state during fetch', async () => {
      const { result } = renderHook(() =>
        useTrackContextMenu({
          track: mockTrack,
          onPlay: mockOnPlay,
        }),
        { wrapper: createWrapper() }
      );

      // Before fetch, loading should be false
      expect(result.current.isLoadingPlaylists).toBe(false);

      // Start fetching
      const fetchPromise = act(() => result.current.fetchPlaylists());

      // After fetch completes, loading should be false again
      await fetchPromise;
      expect(result.current.isLoadingPlaylists).toBe(false);
    });
  });

  describe('handleAddToPlaylist', () => {
    it('should add track to playlist and show success toast', async () => {
      const { result } = renderHook(() =>
        useTrackContextMenu({
          track: mockTrack,
          onPlay: mockOnPlay,
        }),
        { wrapper: createWrapper() }
      );

      vi.mocked(playlistService.addTracksToPlaylist).mockResolvedValue(undefined);

      await act(async () => {
        await result.current.handleAddToPlaylist(1, 'Favorites');
      });

      expect(playlistService.addTracksToPlaylist).toHaveBeenCalledWith(1, [
        mockTrack.id,
      ]);
      expect(mockToastSuccess).toHaveBeenCalledWith('Added to "Favorites"');
    });

    it('should handle API errors', async () => {
      const { result } = renderHook(() =>
        useTrackContextMenu({
          track: mockTrack,
          onPlay: mockOnPlay,
        }),
        { wrapper: createWrapper() }
      );

      const errorMessage = 'API Error';
      vi.mocked(playlistService.addTracksToPlaylist).mockRejectedValue(
        new Error(errorMessage)
      );

      await act(async () => {
        await result.current.handleAddToPlaylist(1, 'Favorites');
      });

      expect(mockToastError).toHaveBeenCalled();
    });
  });

  describe('handleCreatePlaylist', () => {
    it('should create and add to new playlist', async () => {
      const { result } = renderHook(() =>
        useTrackContextMenu({
          track: mockTrack,
          onPlay: mockOnPlay,
        }),
        { wrapper: createWrapper() }
      );

      const newPlaylist = { id: 3, name: 'New Playlist', trackCount: 0 };
      vi.mocked(playlistService.addTracksToPlaylist).mockResolvedValue(undefined);

      await act(async () => {
        await result.current.handleCreatePlaylist(newPlaylist);
      });

      expect(playlistService.addTracksToPlaylist).toHaveBeenCalledWith(3, [
        mockTrack.id,
      ]);
      expect(mockToastSuccess).toHaveBeenCalledWith('Added to "New Playlist"');
    });
  });

  describe('State Isolation', () => {
    it('should not leak position state between instances', async () => {
      const { result: result1 } = renderHook(() =>
        useTrackContextMenu({
          track: mockTrack,
          onPlay: mockOnPlay,
        }),
        { wrapper: createWrapper() }
      );

      const { result: result2 } = renderHook(() =>
        useTrackContextMenu({
          track: { ...mockTrack, id: 2 },
          onPlay: mockOnPlay,
        }),
        { wrapper: createWrapper() }
      );

      const mockEvent1 = {
        clientX: 100,
        clientY: 50,
        stopPropagation: vi.fn(),
      } as unknown as React.MouseEvent;

      const mockEvent2 = {
        clientX: 200,
        clientY: 150,
        stopPropagation: vi.fn(),
      } as unknown as React.MouseEvent;

      await act(async () => {
        result1.current.handleMoreClick(mockEvent1);
        result2.current.handleMoreClick(mockEvent2);
      });

      expect(result1.current.contextMenuPosition).toEqual({
        left: 100,
        top: 50,
      });
      expect(result2.current.contextMenuPosition).toEqual({
        left: 200,
        top: 150,
      });
    });
  });

  describe('Handler Memoization', () => {
    it('should memoize context actions', async () => {
      // Create wrapper once and reuse it for both renders
      const wrapper = createWrapper();

      const { result, rerender } = renderHook(
        ({ track }) =>
          useTrackContextMenu({
            track,
            onPlay: mockOnPlay,
          }),
        {
          initialProps: { track: mockTrack },
          wrapper,
        }
      );

      const initialActions = result.current.contextActions;

      rerender({ track: mockTrack });

      // Same track should maintain referential equality
      expect(result.current.contextActions).toBe(initialActions);
    });
  });
});
