/**
 * useTrackRowSelection - Hook for managing track row selection behavior
 *
 * Handles click events for selection checkbox and row container,
 * preventing selection when clicking on action buttons.
 */

import React, { useCallback } from 'react';

interface UseTrackRowSelectionProps {
  onToggleSelect: (event: React.MouseEvent) => void;
}

export const useTrackRowSelection = ({ onToggleSelect }: UseTrackRowSelectionProps) => {
  /**
   * Handle container click - prevent selection if clicking on action buttons
   */
  const handleContainerClick = useCallback((event: React.MouseEvent) => {
    const target = event.target as HTMLElement;
    const isActionButton = target.closest('button') || target.closest('[role="button"]');

    if (!isActionButton) {
      onToggleSelect(event);
    }
  }, [onToggleSelect]);

  /**
   * Handle checkbox click - prevent event propagation
   */
  const handleCheckboxClick = useCallback((event: React.MouseEvent) => {
    event.stopPropagation();
    onToggleSelect(event);
  }, [onToggleSelect]);

  return {
    handleContainerClick,
    handleCheckboxClick,
  };
};

export default useTrackRowSelection;
