/**
 * MobileSidebarDrawer - Swipeable drawer for mobile navigation
 *
 * Displays sidebar content in a drawer on mobile screens (<900px).
 * Automatically closes after navigation or settings action.
 */

import React from 'react';
import { SwipeableDrawer } from '@mui/material';
import Sidebar from '../layouts/Sidebar';
import { auroraOpacity } from '../library/Styles/Color.styles';

interface MobileSidebarDrawerProps {
  open: boolean;
  onClose: () => void;
  onNavigate: (view: string) => void;
  onOpenSettings: () => void;
}

export const MobileSidebarDrawer: React.FC<MobileSidebarDrawerProps> = ({
  open,
  onClose,
  onNavigate,
  onOpenSettings,
}) => {
  const handleNavigate = (view: string) => {
    onNavigate(view);
    onClose(); // Close drawer after navigation
  };

  const handleSettings = () => {
    onOpenSettings();
    onClose(); // Close drawer after opening settings
  };

  return (
    <SwipeableDrawer
      anchor="left"
      open={open}
      onClose={onClose}
      onOpen={() => {
        // Opening via swipe is handled by drawer
      }}
      disableSwipeToOpen={false}
      swipeAreaWidth={20}
      ModalProps={{
        keepMounted: true, // Better performance on mobile
      }}
      PaperProps={{
        sx: {
          width: 240,
          // Semi-transparent to let starfield show through
          background: 'rgba(16, 23, 41, 0.85)',
          backdropFilter: 'blur(16px) saturate(1.1)',
          borderRight: `1px solid ${auroraOpacity.veryLight}`,
        },
      }}
    >
      <Sidebar
        collapsed={false} // Mobile drawer never collapses
        onNavigate={handleNavigate}
        onOpenSettings={handleSettings}
      />
    </SwipeableDrawer>
  );
};
