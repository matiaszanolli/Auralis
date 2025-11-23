/**
 * useContextMenu Hook
 *
 * Manages context menu state (open/close, position tracking)
 * Provides handlers for showing/hiding context menu on right-click
 */

import { useState } from 'react';

export const useContextMenu = () => {
  const [contextMenuState, setContextMenuState] = useState<{
    isOpen: boolean;
    mousePosition: { top: number; left: number } | undefined;
  }>({
    isOpen: false,
    mousePosition: undefined,
  });

  const handleContextMenu = (event: React.MouseEvent) => {
    event.preventDefault();
    setContextMenuState({
      isOpen: true,
      mousePosition: {
        top: event.clientY,
        left: event.clientX,
      },
    });
  };

  const handleCloseContextMenu = () => {
    setContextMenuState({
      isOpen: false,
      mousePosition: undefined,
    });
  };

  return {
    contextMenuState,
    handleContextMenu,
    handleCloseContextMenu,
  };
};
