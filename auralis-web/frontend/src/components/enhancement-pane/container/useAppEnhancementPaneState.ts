/**
 * useAppEnhancementPaneState Hook
 *
 * Manages collapse/expand state for enhancement pane
 */

import { useState } from 'react';

export const useAppEnhancementPaneState = (initiallyCollapsed: boolean = false) => {
  const [isCollapsed, setIsCollapsed] = useState(initiallyCollapsed);

  const handleCollapsedToggle = () => {
    setIsCollapsed(!isCollapsed);
  };

  return {
    isCollapsed,
    handleCollapsedToggle,
  };
};
