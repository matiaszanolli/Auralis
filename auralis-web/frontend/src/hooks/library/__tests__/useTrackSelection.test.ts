/**
 * useTrackSelection Hook Tests
 *
 * Tests for multi-select track state with keyboard modifier support.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useTrackSelection } from '../useTrackSelection';

const tracks = [
  { id: 1 },
  { id: 2 },
  { id: 3 },
  { id: 4 },
  { id: 5 },
];

/** Helper to create a partial MouseEvent with modifier flags. */
function mouseEvent(opts: Partial<Pick<React.MouseEvent, 'shiftKey' | 'ctrlKey' | 'metaKey'>> = {}) {
  return { shiftKey: false, ctrlKey: false, metaKey: false, ...opts } as React.MouseEvent;
}

describe('useTrackSelection', () => {
  describe('initial state', () => {
    it('starts with empty selection', () => {
      const { result } = renderHook(() => useTrackSelection(tracks));

      expect(result.current.selectedCount).toBe(0);
      expect(result.current.hasSelection).toBe(false);
      expect(result.current.isSelected(1)).toBe(false);
    });
  });

  describe('regular click (toggleTrack)', () => {
    it('selects a single track', () => {
      const { result } = renderHook(() => useTrackSelection(tracks));

      act(() => {
        result.current.toggleTrack(2);
      });

      expect(result.current.isSelected(2)).toBe(true);
      expect(result.current.selectedCount).toBe(1);
    });

    it('replaces previous selection when clicking a different track', () => {
      const { result } = renderHook(() => useTrackSelection(tracks));

      act(() => {
        result.current.toggleTrack(1);
      });

      act(() => {
        result.current.toggleTrack(3);
      });

      expect(result.current.isSelected(1)).toBe(false);
      expect(result.current.isSelected(3)).toBe(true);
      expect(result.current.selectedCount).toBe(1);
    });

    it('deselects when clicking the only selected track', () => {
      const { result } = renderHook(() => useTrackSelection(tracks));

      act(() => {
        result.current.toggleTrack(2);
      });

      act(() => {
        result.current.toggleTrack(2);
      });

      expect(result.current.selectedCount).toBe(0);
    });
  });

  describe('Ctrl/Cmd click', () => {
    it('adds to existing selection', () => {
      const { result } = renderHook(() => useTrackSelection(tracks));

      act(() => {
        result.current.toggleTrack(1);
      });

      act(() => {
        result.current.toggleTrack(3, mouseEvent({ ctrlKey: true }));
      });

      expect(result.current.isSelected(1)).toBe(true);
      expect(result.current.isSelected(3)).toBe(true);
      expect(result.current.selectedCount).toBe(2);
    });

    it('removes from selection when Ctrl-clicking selected track', () => {
      const { result } = renderHook(() => useTrackSelection(tracks));

      act(() => {
        result.current.toggleTrack(1);
      });

      act(() => {
        result.current.toggleTrack(3, mouseEvent({ ctrlKey: true }));
      });

      act(() => {
        result.current.toggleTrack(1, mouseEvent({ ctrlKey: true }));
      });

      expect(result.current.isSelected(1)).toBe(false);
      expect(result.current.isSelected(3)).toBe(true);
      expect(result.current.selectedCount).toBe(1);
    });

    it('supports metaKey (Cmd on Mac)', () => {
      const { result } = renderHook(() => useTrackSelection(tracks));

      act(() => {
        result.current.toggleTrack(1);
      });

      act(() => {
        result.current.toggleTrack(4, mouseEvent({ metaKey: true }));
      });

      expect(result.current.isSelected(1)).toBe(true);
      expect(result.current.isSelected(4)).toBe(true);
    });
  });

  describe('Shift click (range selection)', () => {
    it('selects range between last-selected and current', () => {
      const { result } = renderHook(() => useTrackSelection(tracks));

      // First click sets lastSelectedId
      act(() => {
        result.current.toggleTrack(2);
      });

      // Shift-click to select range 2..4
      act(() => {
        result.current.toggleTrack(4, mouseEvent({ shiftKey: true }));
      });

      expect(result.current.isSelected(2)).toBe(true);
      expect(result.current.isSelected(3)).toBe(true);
      expect(result.current.isSelected(4)).toBe(true);
      expect(result.current.isSelected(1)).toBe(false);
      expect(result.current.isSelected(5)).toBe(false);
    });

    it('selects range in reverse order', () => {
      const { result } = renderHook(() => useTrackSelection(tracks));

      act(() => {
        result.current.toggleTrack(4);
      });

      act(() => {
        result.current.toggleTrack(2, mouseEvent({ shiftKey: true }));
      });

      expect(result.current.isSelected(2)).toBe(true);
      expect(result.current.isSelected(3)).toBe(true);
      expect(result.current.isSelected(4)).toBe(true);
    });
  });

  describe('selectRange', () => {
    it('adds a range of tracks to the selection', () => {
      const { result } = renderHook(() => useTrackSelection(tracks));

      act(() => {
        result.current.selectRange(2, 4);
      });

      expect(result.current.isSelected(2)).toBe(true);
      expect(result.current.isSelected(3)).toBe(true);
      expect(result.current.isSelected(4)).toBe(true);
      expect(result.current.selectedCount).toBe(3);
    });

    it('does nothing when IDs are not in the track list', () => {
      const { result } = renderHook(() => useTrackSelection(tracks));

      act(() => {
        result.current.selectRange(99, 100);
      });

      expect(result.current.selectedCount).toBe(0);
    });
  });

  describe('selectAll', () => {
    it('selects every track', () => {
      const { result } = renderHook(() => useTrackSelection(tracks));

      act(() => {
        result.current.selectAll();
      });

      expect(result.current.selectedCount).toBe(5);
      for (const t of tracks) {
        expect(result.current.isSelected(t.id)).toBe(true);
      }
    });
  });

  describe('clearSelection', () => {
    it('clears all selected tracks', () => {
      const { result } = renderHook(() => useTrackSelection(tracks));

      act(() => {
        result.current.selectAll();
      });

      act(() => {
        result.current.clearSelection();
      });

      expect(result.current.selectedCount).toBe(0);
      expect(result.current.hasSelection).toBe(false);
    });
  });

  describe('track list changes', () => {
    it('adapts to new track list for selectAll', () => {
      const { result, rerender } = renderHook(
        ({ t }) => useTrackSelection(t),
        { initialProps: { t: tracks } }
      );

      // Rerender with different tracks
      rerender({ t: [{ id: 10 }, { id: 20 }] });

      act(() => {
        result.current.selectAll();
      });

      expect(result.current.selectedCount).toBe(2);
      expect(result.current.isSelected(10)).toBe(true);
      expect(result.current.isSelected(20)).toBe(true);
    });
  });
});
