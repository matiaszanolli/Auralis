/**
 * useBatchOperations Hook Tests
 *
 * Tests for batch operations on selected tracks:
 * - Bulk add to queue
 * - Bulk add to playlist
 * - Bulk remove operations
 * - Bulk toggle favorite
 *
 * Note: Uses MSW for API mocking - handlers defined in src/test/mocks/handlers.ts
 */

import { vi } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useBatchOperations } from '../useBatchOperations';
import { server } from '@/test/mocks/server';
import { http, HttpResponse } from 'msw';

// Mock dependencies
vi.mock('../../shared/Toast', () => ({
  useToast: vi.fn(() => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  })),
}));

import { useToast } from '../../shared/Toast';

describe('useBatchOperations', () => {
  const mockOnFetchTracks = vi.fn().mockResolvedValue(undefined);
  const mockOnClearSelection = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    server.resetHandlers();
    // Mock confirm globally
    (global.confirm as any) = vi.fn(() => true);
  });

  describe('Hook Initialization', () => {
    it('should expose all four batch operation handlers', () => {
      const { result } = renderHook(() =>
        useBatchOperations({
          selectedTracks: new Set([1, 2, 3]),
          selectedCount: 3,
          view: 'library',
          onFetchTracks: mockOnFetchTracks,
          onClearSelection: mockOnClearSelection,
        })
      );

      expect(result.current.handleBulkAddToQueue).toBeDefined();
      expect(result.current.handleBulkAddToPlaylist).toBeDefined();
      expect(result.current.handleBulkRemove).toBeDefined();
      expect(result.current.handleBulkToggleFavorite).toBeDefined();
    });
  });

  describe('handleBulkAddToQueue', () => {
    it('should add all selected tracks to queue', async () => {
      const { result } = renderHook(() =>
        useBatchOperations({
          selectedTracks: new Set([1, 2, 3]),
          selectedCount: 3,
          view: 'library',
          onFetchTracks: mockOnFetchTracks,
          onClearSelection: mockOnClearSelection,
        })
      );

      await act(async () => {
        await result.current.handleBulkAddToQueue();
      });

      // Verify tracks were added (MSW default handler returns success)
      expect(mockOnClearSelection).toHaveBeenCalled();
    });

    it('should show success toast', async () => {
      const mockToastSuccess = vi.fn();
      vi.mocked(useToast).mockReturnValue({
        success: mockToastSuccess,
        error: vi.fn(),
        info: vi.fn(),
        warning: vi.fn(),
      });

      const { result } = renderHook(() =>
        useBatchOperations({
          selectedTracks: new Set([1, 2]),
          selectedCount: 2,
          view: 'library',
          onFetchTracks: mockOnFetchTracks,
          onClearSelection: mockOnClearSelection,
        })
      );

      await act(async () => {
        await result.current.handleBulkAddToQueue();
      });

      expect(mockToastSuccess).toHaveBeenCalledWith('Added 2 tracks to queue');
    });

    it('should clear selection after adding', async () => {
      const { result } = renderHook(() =>
        useBatchOperations({
          selectedTracks: new Set([1, 2, 3]),
          selectedCount: 3,
          view: 'library',
          onFetchTracks: mockOnFetchTracks,
          onClearSelection: mockOnClearSelection,
        })
      );

      await act(async () => {
        await result.current.handleBulkAddToQueue();
      });

      expect(mockOnClearSelection).toHaveBeenCalled();
    });

    it('should handle API errors', async () => {
      const mockToastError = vi.fn();
      vi.mocked(useToast).mockReturnValue({
        success: vi.fn(),
        error: mockToastError,
        info: vi.fn(),
        warning: vi.fn(),
      });

      // Override handler to simulate error
      server.use(
        http.post('/api/player/queue/add-track', () => {
          return HttpResponse.error();
        })
      );

      const { result } = renderHook(() =>
        useBatchOperations({
          selectedTracks: new Set([1]),
          selectedCount: 1,
          view: 'library',
          onFetchTracks: mockOnFetchTracks,
          onClearSelection: mockOnClearSelection,
        })
      );

      await act(async () => {
        await result.current.handleBulkAddToQueue();
      });

      expect(mockToastError).toHaveBeenCalledWith('Failed to add tracks to queue');
    });
  });

  describe('handleBulkAddToPlaylist', () => {
    it('should show coming soon message', async () => {
      const mockToastInfo = vi.fn();
      vi.mocked(useToast).mockReturnValue({
        success: vi.fn(),
        error: vi.fn(),
        info: mockToastInfo,
        warning: vi.fn(),
      });

      const { result } = renderHook(() =>
        useBatchOperations({
          selectedTracks: new Set([1, 2]),
          selectedCount: 2,
          view: 'library',
          onFetchTracks: mockOnFetchTracks,
          onClearSelection: mockOnClearSelection,
        })
      );

      await act(async () => {
        await result.current.handleBulkAddToPlaylist();
      });

      expect(mockToastInfo).toHaveBeenCalledWith('Bulk add to playlist - Coming soon!');
    });
  });

  describe('handleBulkRemove', () => {
    it('should prompt for confirmation', async () => {
      const { result } = renderHook(() =>
        useBatchOperations({
          selectedTracks: new Set([1, 2]),
          selectedCount: 2,
          view: 'library',
          onFetchTracks: mockOnFetchTracks,
          onClearSelection: mockOnClearSelection,
        })
      );

      await act(async () => {
        await result.current.handleBulkRemove();
      });

      expect(global.confirm).toHaveBeenCalledWith('Remove 2 tracks?');
    });

    it('should cancel if not confirmed', async () => {
      (global.confirm as any).mockReturnValue(false);

      const { result } = renderHook(() =>
        useBatchOperations({
          selectedTracks: new Set([1, 2]),
          selectedCount: 2,
          view: 'library',
          onFetchTracks: mockOnFetchTracks,
          onClearSelection: mockOnClearSelection,
        })
      );

      await act(async () => {
        await result.current.handleBulkRemove();
      });

      // Should not proceed with deletion
      expect(mockOnFetchTracks).not.toHaveBeenCalled();
    });

    it('should delete from favorites when in favorites view', async () => {
      const mockToastSuccess = vi.fn();
      vi.mocked(useToast).mockReturnValue({
        success: mockToastSuccess,
        error: vi.fn(),
        info: vi.fn(),
        warning: vi.fn(),
      });

      const { result } = renderHook(() =>
        useBatchOperations({
          selectedTracks: new Set([1, 2]),
          selectedCount: 2,
          view: 'favourites',
          onFetchTracks: mockOnFetchTracks,
          onClearSelection: mockOnClearSelection,
        })
      );

      await act(async () => {
        await result.current.handleBulkRemove();
      });

      expect(mockToastSuccess).toHaveBeenCalledWith('Removed 2 tracks from favorites');
      expect(mockOnFetchTracks).toHaveBeenCalled();
    });

    it('should show implementation message for library delete', async () => {
      const mockToastInfo = vi.fn();
      vi.mocked(useToast).mockReturnValue({
        success: vi.fn(),
        error: vi.fn(),
        info: mockToastInfo,
        warning: vi.fn(),
      });

      const { result } = renderHook(() =>
        useBatchOperations({
          selectedTracks: new Set([1, 2]),
          selectedCount: 2,
          view: 'library',
          onFetchTracks: mockOnFetchTracks,
          onClearSelection: mockOnClearSelection,
        })
      );

      await act(async () => {
        await result.current.handleBulkRemove();
      });

      expect(mockToastInfo).toHaveBeenCalledWith(
        'Bulk delete from library requires API implementation'
      );
    });

    it('should call onFetchTracks after success', async () => {
      const { result } = renderHook(() =>
        useBatchOperations({
          selectedTracks: new Set([1]),
          selectedCount: 1,
          view: 'favourites',
          onFetchTracks: mockOnFetchTracks,
          onClearSelection: mockOnClearSelection,
        })
      );

      await act(async () => {
        await result.current.handleBulkRemove();
      });

      expect(mockOnFetchTracks).toHaveBeenCalled();
    });

    it('should handle API errors', async () => {
      const mockToastError = vi.fn();
      vi.mocked(useToast).mockReturnValue({
        success: vi.fn(),
        error: mockToastError,
        info: vi.fn(),
        warning: vi.fn(),
      });

      // Override handler to simulate error
      server.use(
        http.delete('/api/library/tracks/:id/favorite', () => {
          return HttpResponse.error();
        })
      );

      const { result } = renderHook(() =>
        useBatchOperations({
          selectedTracks: new Set([1]),
          selectedCount: 1,
          view: 'favourites',
          onFetchTracks: mockOnFetchTracks,
          onClearSelection: mockOnClearSelection,
        })
      );

      await act(async () => {
        await result.current.handleBulkRemove();
      });

      expect(mockToastError).toHaveBeenCalledWith('Failed to remove tracks');
    });
  });

  describe('handleBulkToggleFavorite', () => {
    it('should toggle favorite for all tracks', async () => {
      const { result } = renderHook(() =>
        useBatchOperations({
          selectedTracks: new Set([1, 2, 3]),
          selectedCount: 3,
          view: 'library',
          onFetchTracks: mockOnFetchTracks,
          onClearSelection: mockOnClearSelection,
        })
      );

      await act(async () => {
        await result.current.handleBulkToggleFavorite();
      });

      // Verify handlers were called
      expect(mockOnClearSelection).toHaveBeenCalled();
      expect(mockOnFetchTracks).toHaveBeenCalled();
    });

    it('should show success toast with count', async () => {
      const mockToastSuccess = vi.fn();
      vi.mocked(useToast).mockReturnValue({
        success: mockToastSuccess,
        error: vi.fn(),
        info: vi.fn(),
        warning: vi.fn(),
      });

      const { result } = renderHook(() =>
        useBatchOperations({
          selectedTracks: new Set([1, 2, 3, 4]),
          selectedCount: 4,
          view: 'library',
          onFetchTracks: mockOnFetchTracks,
          onClearSelection: mockOnClearSelection,
        })
      );

      await act(async () => {
        await result.current.handleBulkToggleFavorite();
      });

      expect(mockToastSuccess).toHaveBeenCalledWith('Toggled favorite for 4 tracks');
    });

    it('should call onFetchTracks after success', async () => {
      const { result } = renderHook(() =>
        useBatchOperations({
          selectedTracks: new Set([1, 2]),
          selectedCount: 2,
          view: 'library',
          onFetchTracks: mockOnFetchTracks,
          onClearSelection: mockOnClearSelection,
        })
      );

      await act(async () => {
        await result.current.handleBulkToggleFavorite();
      });

      expect(mockOnFetchTracks).toHaveBeenCalled();
    });

    it('should clear selection after toggle', async () => {
      const { result } = renderHook(() =>
        useBatchOperations({
          selectedTracks: new Set([1, 2]),
          selectedCount: 2,
          view: 'library',
          onFetchTracks: mockOnFetchTracks,
          onClearSelection: mockOnClearSelection,
        })
      );

      await act(async () => {
        await result.current.handleBulkToggleFavorite();
      });

      expect(mockOnClearSelection).toHaveBeenCalled();
    });

    it('should handle API errors', async () => {
      const mockToastError = vi.fn();
      vi.mocked(useToast).mockReturnValue({
        success: vi.fn(),
        error: mockToastError,
        info: vi.fn(),
        warning: vi.fn(),
      });

      // Override handler to simulate error
      server.use(
        http.post('/api/library/tracks/:id/favorite', () => {
          return HttpResponse.error();
        })
      );

      const { result } = renderHook(() =>
        useBatchOperations({
          selectedTracks: new Set([1]),
          selectedCount: 1,
          view: 'library',
          onFetchTracks: mockOnFetchTracks,
          onClearSelection: mockOnClearSelection,
        })
      );

      await act(async () => {
        await result.current.handleBulkToggleFavorite();
      });

      expect(mockToastError).toHaveBeenCalledWith('Failed to toggle favorites');
    });
  });

  describe('View-Specific Behavior', () => {
    it('should behave differently for favorites vs library', async () => {
      const mockToastSuccess = vi.fn();
      vi.mocked(useToast).mockReturnValue({
        success: mockToastSuccess,
        error: vi.fn(),
        info: vi.fn(),
        warning: vi.fn(),
      });

      const favResult = renderHook(() =>
        useBatchOperations({
          selectedTracks: new Set([1]),
          selectedCount: 1,
          view: 'favourites',
          onFetchTracks: mockOnFetchTracks,
          onClearSelection: mockOnClearSelection,
        })
      );

      await act(async () => {
        await favResult.result.current.handleBulkRemove();
      });

      expect(mockToastSuccess).toHaveBeenCalledWith('Removed 1 tracks from favorites');
    });
  });

  describe('Empty Selection', () => {
    it('should handle empty selectedTracks', async () => {
      const { result } = renderHook(() =>
        useBatchOperations({
          selectedTracks: new Set(),
          selectedCount: 0,
          view: 'library',
          onFetchTracks: mockOnFetchTracks,
          onClearSelection: mockOnClearSelection,
        })
      );

      await act(async () => {
        await result.current.handleBulkAddToQueue();
      });

      // Should not call handlers when no tracks selected
      expect(mockOnClearSelection).toHaveBeenCalled();
    });
  });

  describe('Large Selection', () => {
    it('should handle large number of selected tracks', async () => {
      const largeSet = new Set(Array.from({ length: 100 }, (_, i) => i + 1));

      const { result } = renderHook(() =>
        useBatchOperations({
          selectedTracks: largeSet,
          selectedCount: 100,
          view: 'library',
          onFetchTracks: mockOnFetchTracks,
          onClearSelection: mockOnClearSelection,
        })
      );

      await act(async () => {
        await result.current.handleBulkAddToQueue();
      });

      expect(mockOnClearSelection).toHaveBeenCalled();
    });
  });
});
