/**
 * useTrackCardState Hook
 *
 * Manages hover state for TrackCard
 */

import { useState } from 'react';

export const useTrackCardState = () => {
  const [isHovered, setIsHovered] = useState(false);

  return {
    isHovered,
    setIsHovered,
  };
};
