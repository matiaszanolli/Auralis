/**
 * useContextMenu Hook
 *
 * Manages context menu state (open/close, position tracking)
 * Provides handlers for showing/hiding context menu on right-click.
 *
 * Both handlers keep a stable identity (#5389): consumers pass them, or
 * callbacks built on them, down to memoized list rows, and a fresh function
 * per render would re-render every row whenever the menu opens or closes.
 */

import { useCallback, useState } from 'react';

export const useContextMenu = () => {
  const [contextMenuState, setContextMenuState] = useState<{
    isOpen: boolean;
    mousePosition: { top: number; left: number } | undefined;
  }>({
    isOpen: false,
    mousePosition: undefined,
  });

  const handleContextMenu = useCallback((event: React.MouseEvent) => {
    event.preventDefault();
    setContextMenuState({
      isOpen: true,
      mousePosition: {
        top: event.clientY,
        left: event.clientX,
      },
    });
  }, []);

  const handleCloseContextMenu = useCallback(() => {
    setContextMenuState({
      isOpen: false,
      mousePosition: undefined,
    });
  }, []);

  return {
    contextMenuState,
    handleContextMenu,
    handleCloseContextMenu,
  };
};
