/**
 * MobileSidebarDrawer - Swipeable drawer for mobile navigation
 *
 * Displays sidebar content in a drawer on mobile screens (<900px).
 * Automatically closes after navigation or settings action.
 */

import React from 'react';
import { SwipeableDrawer } from '@mui/material';
import Sidebar from '../layouts/Sidebar';

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
          background: 'rgba(16, 23, 41, 0.55)',
          backdropFilter: 'blur(8px) saturate(1.05)',
          // Glass bevel: right highlight + inner shadow (no hard borders)
          boxShadow: '2px 0 16px rgba(0, 0, 0, 0.12), inset -1px 0 0 rgba(255, 255, 255, 0.06)',
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
