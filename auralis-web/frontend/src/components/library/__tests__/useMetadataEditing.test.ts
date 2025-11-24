/**
 * useMetadataEditing Hook Tests
 *
 * Tests for metadata editing dialog state:
 * - Dialog open/close management
 * - Track ID tracking
 * - Save and close handlers
 */

import { vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useMetadataEditing } from '../useMetadataEditing';

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

describe('useMetadataEditing', () => {
  const mockOnFetchTracks = vi.fn().mockResolvedValue(undefined);

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Hook Initialization', () => {
    it('should initialize with dialog closed and null trackId', () => {
      const { result } = renderHook(() =>
        useMetadataEditing(mockOnFetchTracks)
      );

      expect(result.current.editMetadataDialogOpen).toBe(false);
      expect(result.current.editingTrackId).toBeNull();
    });
  });

  describe('handleEditMetadata', () => {
    it('should set trackId and open dialog', async () => {
      const { result } = renderHook(() =>
        useMetadataEditing(mockOnFetchTracks)
      );

      act(() => {
        result.current.handleEditMetadata(42);
      });

      expect(result.current.editingTrackId).toBe(42);
      expect(result.current.editMetadataDialogOpen).toBe(true);
    });

    it('should update trackId on multiple calls', () => {
      const { result } = renderHook(() =>
        useMetadataEditing(mockOnFetchTracks)
      );

      act(() => {
        result.current.handleEditMetadata(1);
      });

      expect(result.current.editingTrackId).toBe(1);
      expect(result.current.editMetadataDialogOpen).toBe(true);

      act(() => {
        result.current.handleEditMetadata(2);
      });

      expect(result.current.editingTrackId).toBe(2);
      expect(result.current.editMetadataDialogOpen).toBe(true);
    });
  });

  describe('handleCloseEditDialog', () => {
    it('should close dialog and reset trackId', async () => {
      const { result } = renderHook(() =>
        useMetadataEditing(mockOnFetchTracks)
      );

      // Open dialog
      act(() => {
        result.current.handleEditMetadata(1);
      });

      expect(result.current.editMetadataDialogOpen).toBe(true);
      expect(result.current.editingTrackId).toBe(1);

      // Close dialog
      act(() => {
        result.current.handleCloseEditDialog();
      });

      expect(result.current.editMetadataDialogOpen).toBe(false);
      expect(result.current.editingTrackId).toBeNull();
    });
  });

  describe('handleSaveMetadata', () => {
    it('should call onFetchTracks', async () => {
      const { result } = renderHook(() =>
        useMetadataEditing(mockOnFetchTracks)
      );

      await act(async () => {
        await result.current.handleSaveMetadata();
      });

      expect(mockOnFetchTracks).toHaveBeenCalled();
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
        useMetadataEditing(mockOnFetchTracks)
      );

      await act(async () => {
        await result.current.handleSaveMetadata();
      });

      expect(mockToastSuccess).toHaveBeenCalledWith('Metadata updated successfully');
    });

    it('should handle async onFetchTracks error', async () => {
      const mockFailedFetch = vi.fn().mockRejectedValue(new Error('Fetch failed'));

      const { result } = renderHook(() =>
        useMetadataEditing(mockFailedFetch)
      );

      await expect(
        act(async () => {
          await result.current.handleSaveMetadata();
        })
      ).rejects.toThrow('Fetch failed');
    });
  });

  describe('Dialog State Management', () => {
    it('should have open true after handleEditMetadata', () => {
      const { result } = renderHook(() =>
        useMetadataEditing(mockOnFetchTracks)
      );

      act(() => {
        result.current.handleEditMetadata(1);
      });

      expect(result.current.editMetadataDialogOpen).toBe(true);
    });

    it('should have open false after handleCloseEditDialog', () => {
      const { result } = renderHook(() =>
        useMetadataEditing(mockOnFetchTracks)
      );

      act(() => {
        result.current.handleEditMetadata(1);
        result.current.handleCloseEditDialog();
      });

      expect(result.current.editMetadataDialogOpen).toBe(false);
    });
  });

  describe('Handler Memoization', () => {
    it('should memoize all handlers with same props', () => {
      const { result, rerender } = renderHook(
        ({ onFetch }) => useMetadataEditing(onFetch),
        { initialProps: { onFetch: mockOnFetchTracks } }
      );

      const initialHandlers = {
        edit: result.current.handleEditMetadata,
        close: result.current.handleCloseEditDialog,
      };

      rerender({ onFetch: mockOnFetchTracks });

      // Non-async handlers should maintain referential equality
      expect(result.current.handleEditMetadata).toBe(initialHandlers.edit);
      expect(result.current.handleCloseEditDialog).toBe(initialHandlers.close);
    });

    it('should update handleSaveMetadata when onFetchTracks changes', () => {
      const oldFetch = vi.fn();
      const newFetch = vi.fn();

      const { result, rerender } = renderHook(
        ({ onFetch }) => useMetadataEditing(onFetch),
        { initialProps: { onFetch: oldFetch } }
      );

      const initialSave = result.current.handleSaveMetadata;

      rerender({ onFetch: newFetch });

      // Should be recreated when dependency changes
      expect(result.current.handleSaveMetadata).not.toBe(initialSave);
    });
  });

  describe('Complete Edit Flow', () => {
    it('should handle complete metadata edit flow', async () => {
      const { result } = renderHook(() =>
        useMetadataEditing(mockOnFetchTracks)
      );

      // Initial state
      expect(result.current.editMetadataDialogOpen).toBe(false);
      expect(result.current.editingTrackId).toBeNull();

      // User opens edit dialog
      act(() => {
        result.current.handleEditMetadata(123);
      });

      expect(result.current.editMetadataDialogOpen).toBe(true);
      expect(result.current.editingTrackId).toBe(123);

      // User saves metadata
      await act(async () => {
        await result.current.handleSaveMetadata();
      });

      expect(mockOnFetchTracks).toHaveBeenCalled();

      // Dialog should still be open (close must be called separately)
      expect(result.current.editMetadataDialogOpen).toBe(true);

      // User closes dialog
      act(() => {
        result.current.handleCloseEditDialog();
      });

      expect(result.current.editMetadataDialogOpen).toBe(false);
      expect(result.current.editingTrackId).toBeNull();
    });

    it('should allow cancel without saving', () => {
      const { result } = renderHook(() =>
        useMetadataEditing(mockOnFetchTracks)
      );

      // Open edit dialog
      act(() => {
        result.current.handleEditMetadata(1);
      });

      expect(result.current.editMetadataDialogOpen).toBe(true);

      // Cancel without saving
      act(() => {
        result.current.handleCloseEditDialog();
      });

      expect(mockOnFetchTracks).not.toHaveBeenCalled();
      expect(result.current.editMetadataDialogOpen).toBe(false);
    });
  });

  describe('Props Integration', () => {
    it('should pass correct values to handlers', async () => {
      const mockFetch = vi.fn().mockResolvedValue(undefined);

      const { result } = renderHook(() =>
        useMetadataEditing(mockFetch)
      );

      act(() => {
        result.current.handleEditMetadata(99);
      });

      expect(result.current.editingTrackId).toBe(99);

      await act(async () => {
        await result.current.handleSaveMetadata();
      });

      expect(mockFetch).toHaveBeenCalled();
    });
  });

  describe('Edge Cases', () => {
    it('should handle zero trackId', () => {
      const { result } = renderHook(() =>
        useMetadataEditing(mockOnFetchTracks)
      );

      act(() => {
        result.current.handleEditMetadata(0);
      });

      expect(result.current.editingTrackId).toBe(0);
      expect(result.current.editMetadataDialogOpen).toBe(true);
    });

    it('should handle negative trackId', () => {
      const { result } = renderHook(() =>
        useMetadataEditing(mockOnFetchTracks)
      );

      act(() => {
        result.current.handleEditMetadata(-1);
      });

      expect(result.current.editingTrackId).toBe(-1);
      expect(result.current.editMetadataDialogOpen).toBe(true);
    });

    it('should handle rapid open/close cycles', () => {
      const { result } = renderHook(() =>
        useMetadataEditing(mockOnFetchTracks)
      );

      act(() => {
        result.current.handleEditMetadata(1);
        result.current.handleCloseEditDialog();
        result.current.handleEditMetadata(2);
        result.current.handleCloseEditDialog();
        result.current.handleEditMetadata(3);
      });

      expect(result.current.editingTrackId).toBe(3);
      expect(result.current.editMetadataDialogOpen).toBe(true);
    });
  });
});
