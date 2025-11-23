/**
 * useBatchActionsMenu Hook
 *
 * Manages the "More Actions" menu state for batch operations
 */

import { useState } from 'react';

export const useBatchActionsMenu = () => {
  const [moreMenuAnchor, setMoreMenuAnchor] = useState<null | HTMLElement>(null);

  const handleMoreMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setMoreMenuAnchor(event.currentTarget);
  };

  const handleMoreMenuClose = () => {
    setMoreMenuAnchor(null);
  };

  const handleAction = (action: () => void) => {
    action();
    handleMoreMenuClose();
  };

  return {
    moreMenuAnchor,
    handleMoreMenuOpen,
    handleMoreMenuClose,
    handleAction,
  };
};
