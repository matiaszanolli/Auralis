/**
 * useTrackRowHandlers Hook Tests
 *
 * Tests for track row interaction handlers:
 * - Play/pause button clicks
 * - Row selection and double-click
 * - Event propagation prevention
 */

import { vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useTrackRowHandlers } from '../useTrackRowHandlers';

describe('useTrackRowHandlers', () => {
  const mockOnPlay = vi.fn();
  const mockOnPause = vi.fn();
  const mockOnDoubleClick = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Hook Initialization', () => {
    it('should initialize with default handler functions', () => {
      const { result } = renderHook(() =>
        useTrackRowHandlers({
          trackId: 1,
          isCurrent: false,
          isPlaying: false,
          onPlay: mockOnPlay,
        })
      );

      expect(result.current.handlePlayClick).toBeDefined();
      expect(result.current.handleRowClick).toBeDefined();
      expect(result.current.handleRowDoubleClick).toBeDefined();
    });
  });

  describe('handlePlayClick', () => {
    it('should call onPlay when track is not currently playing', () => {
      const { result } = renderHook(() =>
        useTrackRowHandlers({
          trackId: 1,
          isCurrent: false,
          isPlaying: false,
          onPlay: mockOnPlay,
          onPause: mockOnPause,
        })
      );

      const mockEvent = {
        stopPropagation: vi.fn(),
      } as unknown as React.MouseEvent;

      result.current.handlePlayClick(mockEvent);

      expect(mockOnPlay).toHaveBeenCalledWith(1);
      expect(mockOnPause).not.toHaveBeenCalled();
      expect(mockEvent.stopPropagation).toHaveBeenCalled();
    });

    it('should call onPause when track is currently playing', () => {
      const { result } = renderHook(() =>
        useTrackRowHandlers({
          trackId: 1,
          isCurrent: true,
          isPlaying: true,
          onPlay: mockOnPlay,
          onPause: mockOnPause,
        })
      );

      const mockEvent = {
        stopPropagation: vi.fn(),
      } as unknown as React.MouseEvent;

      result.current.handlePlayClick(mockEvent);

      expect(mockOnPause).toHaveBeenCalled();
      expect(mockOnPlay).not.toHaveBeenCalled();
      expect(mockEvent.stopPropagation).toHaveBeenCalled();
    });

    it('should prevent default event propagation', () => {
      const { result } = renderHook(() =>
        useTrackRowHandlers({
          trackId: 1,
          isCurrent: false,
          isPlaying: false,
          onPlay: mockOnPlay,
        })
      );

      const mockEvent = {
        stopPropagation: vi.fn(),
      } as unknown as React.MouseEvent;

      result.current.handlePlayClick(mockEvent);

      expect(mockEvent.stopPropagation).toHaveBeenCalled();
    });
  });

  describe('handleRowClick', () => {
    it('should call onPlay with track ID', () => {
      const { result } = renderHook(() =>
        useTrackRowHandlers({
          trackId: 42,
          isCurrent: false,
          isPlaying: false,
          onPlay: mockOnPlay,
        })
      );

      result.current.handleRowClick();

      expect(mockOnPlay).toHaveBeenCalledWith(42);
    });
  });

  describe('handleRowDoubleClick', () => {
    it('should call onDoubleClick callback with track ID', () => {
      const { result } = renderHook(() =>
        useTrackRowHandlers({
          trackId: 1,
          isCurrent: false,
          isPlaying: false,
          onPlay: mockOnPlay,
          onDoubleClick: mockOnDoubleClick,
        })
      );

      result.current.handleRowDoubleClick();

      expect(mockOnDoubleClick).toHaveBeenCalledWith(1);
    });

    it('should handle undefined onDoubleClick gracefully', () => {
      const { result } = renderHook(() =>
        useTrackRowHandlers({
          trackId: 1,
          isCurrent: false,
          isPlaying: false,
          onPlay: mockOnPlay,
          // onDoubleClick is not provided
        })
      );

      expect(() => {
        result.current.handleRowDoubleClick();
      }).not.toThrow();
    });
  });

  describe('Handler Stability', () => {
    it('should maintain referential equality across renders', () => {
      const { result, rerender } = renderHook(
        ({ trackId, isCurrent, isPlaying }) =>
          useTrackRowHandlers({
            trackId,
            isCurrent,
            isPlaying,
            onPlay: mockOnPlay,
          }),
        {
          initialProps: {
            trackId: 1,
            isCurrent: false,
            isPlaying: false,
          },
        }
      );

      const initialHandlers = {
        play: result.current.handlePlayClick,
        row: result.current.handleRowClick,
        double: result.current.handleRowDoubleClick,
      };

      // Rerender with same props
      rerender({ trackId: 1, isCurrent: false, isPlaying: false });

      expect(result.current.handlePlayClick).toBe(initialHandlers.play);
      expect(result.current.handleRowClick).toBe(initialHandlers.row);
      expect(result.current.handleRowDoubleClick).toBe(initialHandlers.double);
    });

    it('should update handlers when dependencies change', () => {
      const { result, rerender } = renderHook(
        ({ trackId, isCurrent, isPlaying }) =>
          useTrackRowHandlers({
            trackId,
            isCurrent,
            isPlaying,
            onPlay: mockOnPlay,
          }),
        {
          initialProps: {
            trackId: 1,
            isCurrent: false,
            isPlaying: false,
          },
        }
      );

      const initialPlayHandler = result.current.handlePlayClick;

      // Rerender with different trackId
      rerender({ trackId: 2, isCurrent: false, isPlaying: false });

      // Handlers should be recreated when trackId changes
      expect(result.current.handlePlayClick).not.toBe(initialPlayHandler);
    });
  });
});
