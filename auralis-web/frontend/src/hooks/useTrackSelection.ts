/**
 * useTrackSelection Hook
 *
 * Manages multi-select state for tracks with Shift/Ctrl selection support.
 *
 * Usage:
 * ```tsx
 * const {
 *   selectedTracks,
 *   isSelected,
 *   toggleTrack,
 *   selectRange,
 *   selectAll,
 *   clearSelection,
 *   selectedCount
 * } = useTrackSelection(tracks);
 * ```
 *
 * Features:
 * - Click to toggle single track
 * - Shift+Click to select range
 * - Ctrl/Cmd+Click to toggle without clearing others
 * - Select all / Clear all
 * - Efficient Set-based selection tracking
 */

import { useState, useCallback, useMemo } from 'react';

interface Track {
  id: number;
  [key: string]: any;
}

export interface UseTrackSelectionReturn {
  selectedTracks: Set<number>;
  isSelected: (trackId: number) => boolean;
  toggleTrack: (trackId: number, event?: React.MouseEvent) => void;
  selectRange: (startId: number, endId: number) => void;
  selectAll: () => void;
  clearSelection: () => void;
  selectedCount: number;
  hasSelection: boolean;
}

/**
 * Hook for managing track selection state
 */
export const useTrackSelection = (tracks: Track[]): UseTrackSelectionReturn => {
  const [selectedTracks, setSelectedTracks] = useState<Set<number>>(new Set());
  const [lastSelectedId, setLastSelectedId] = useState<number | null>(null);

  // Check if a track is selected
  const isSelected = useCallback(
    (trackId: number): boolean => {
      return selectedTracks.has(trackId);
    },
    [selectedTracks]
  );

  // Toggle single track selection
  const toggleTrack = useCallback(
    (trackId: number, event?: React.MouseEvent) => {
      setSelectedTracks((prev) => {
        const newSelection = new Set(prev);

        if (event?.shiftKey && lastSelectedId !== null) {
          // Shift+Click: Select range
          const trackIds = tracks.map(t => t.id);
          const startIndex = trackIds.indexOf(lastSelectedId);
          const endIndex = trackIds.indexOf(trackId);

          if (startIndex !== -1 && endIndex !== -1) {
            const [min, max] = [Math.min(startIndex, endIndex), Math.max(startIndex, endIndex)];
            for (let i = min; i <= max; i++) {
              newSelection.add(trackIds[i]);
            }
          }
        } else if (event?.ctrlKey || event?.metaKey) {
          // Ctrl/Cmd+Click: Toggle without clearing others
          if (newSelection.has(trackId)) {
            newSelection.delete(trackId);
          } else {
            newSelection.add(trackId);
          }
        } else {
          // Regular click: Toggle single track (clear others)
          if (newSelection.has(trackId) && newSelection.size === 1) {
            // If clicking the only selected track, deselect it
            newSelection.clear();
          } else {
            // Select only this track
            newSelection.clear();
            newSelection.add(trackId);
          }
        }

        setLastSelectedId(trackId);
        return newSelection;
      });
    },
    [tracks, lastSelectedId]
  );

  // Select range of tracks
  const selectRange = useCallback(
    (startId: number, endId: number) => {
      setSelectedTracks((prev) => {
        const newSelection = new Set(prev);
        const trackIds = tracks.map(t => t.id);
        const startIndex = trackIds.indexOf(startId);
        const endIndex = trackIds.indexOf(endId);

        if (startIndex !== -1 && endIndex !== -1) {
          const [min, max] = [Math.min(startIndex, endIndex), Math.max(startIndex, endIndex)];
          for (let i = min; i <= max; i++) {
            newSelection.add(trackIds[i]);
          }
        }

        return newSelection;
      });
    },
    [tracks]
  );

  // Select all tracks
  const selectAll = useCallback(() => {
    setSelectedTracks(new Set(tracks.map(t => t.id)));
  }, [tracks]);

  // Clear selection
  const clearSelection = useCallback(() => {
    setSelectedTracks(new Set());
    setLastSelectedId(null);
  }, []);

  // Computed properties
  const selectedCount = useMemo(() => selectedTracks.size, [selectedTracks]);
  const hasSelection = useMemo(() => selectedTracks.size > 0, [selectedTracks]);

  return {
    selectedTracks,
    isSelected,
    toggleTrack,
    selectRange,
    selectAll,
    clearSelection,
    selectedCount,
    hasSelection,
  };
};

export default useTrackSelection;
