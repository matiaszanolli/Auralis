/**
 * useMediaCardState Hook
 * ~~~~~~~~~~~~~~~~~~~~~~
 *
 * Manages hover state for MediaCard component.
 * Extracted from TrackCard's useTrackCardState for reusability.
 */

import { useState } from 'react';

export interface MediaCardState {
  isHovered: boolean;
  setIsHovered: (hovered: boolean) => void;
}

/**
 * Hook for managing media card hover state
 */
export const useMediaCardState = (): MediaCardState => {
  const [isHovered, setIsHovered] = useState(false);

  return {
    isHovered,
    setIsHovered,
  };
};
