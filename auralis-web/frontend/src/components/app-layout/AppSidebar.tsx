import React from 'react';
import {
  Box,
  SwipeableDrawer,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import Sidebar from '../Sidebar';
import { auroraOpacity } from '../library/Color.styles';

/**
 * Props for the AppSidebar component.
 */
export interface AppSidebarProps {
  /**
   * Whether sidebar is collapsed (desktop only).
   * On mobile, the drawer is used instead of a collapsible sidebar.
   */
  collapsed: boolean;

  /**
   * Callback when toggle collapse button is clicked (desktop only).
   */
  onToggleCollapse: () => void;

  /**
   * Callback when a navigation item is selected.
   * Receives the view name (e.g., 'songs', 'albums', 'artists').
   */
  onNavigate: (view: string) => void;

  /**
   * Callback when settings button is clicked.
   */
  onOpenSettings: () => void;

  /**
   * Whether mobile drawer is open.
   * Only applicable on mobile screens.
   */
  mobileDrawerOpen: boolean;

  /**
   * Callback to close mobile drawer.
   * Only applicable on mobile screens.
   */
  onCloseMobileDrawer: () => void;

  /**
   * Whether current screen is mobile (<900px).
   * Determines whether to show sidebar or mobile drawer.
   */
  isMobile: boolean;
}

/**
 * AppSidebar component handles both desktop sidebar and mobile drawer.
 *
 * Responsibilities:
 * - Desktop: Display collapsible sidebar with navigation
 * - Mobile: Display swipeable drawer with navigation
 * - Both: Handle navigation callbacks, settings button, collapse toggle
 *
 * Responsive Behavior:
 * - Mobile (<900px): Shows swipeable drawer on left side
 * - Desktop (≥900px): Shows fixed sidebar with collapse toggle
 *
 * @param props Component props
 * @returns Rendered sidebar or mobile drawer based on screen size
 *
 * @example
 * ```tsx
 * function ComfortableApp() {
 *   const layout = useAppLayout();
 *
 *   return (
 *     <>
 *       <AppSidebar
 *         collapsed={layout.sidebarCollapsed}
 *         onToggleCollapse={layout.toggleSidebarCollapse}
 *         onNavigate={handleNavigation}
 *         onOpenSettings={handleOpenSettings}
 *         mobileDrawerOpen={layout.mobileDrawerOpen}
 *         onCloseMobileDrawer={layout.toggleMobileDrawer}
 *         isMobile={layout.isMobile}
 *       />
 *     </>
 *   );
 * }
 * ```
 */
export const AppSidebar: React.FC<AppSidebarProps> = ({
  collapsed,
  onToggleCollapse,
  onNavigate,
  onOpenSettings,
  mobileDrawerOpen,
  onCloseMobileDrawer,
  isMobile,
}) => {
  const theme = useTheme();
  const mediaIsMobile = useMediaQuery(theme.breakpoints.down('md'));

  // Handle responsive behavior in case isMobile prop doesn't match media query
  const shouldShowMobileDrawer = isMobile || mediaIsMobile;

  if (shouldShowMobileDrawer) {
    // ========================================
    // MOBILE: Swipeable Drawer
    // ========================================
    return (
      <SwipeableDrawer
        anchor="left"
        open={mobileDrawerOpen}
        onClose={onCloseMobileDrawer}
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
            background: 'var(--midnight-blue)',
            borderRight: `1px solid ${auroraOpacity.veryLight}`,
          },
        }}
      >
        <Sidebar
          collapsed={false} // Mobile drawer never collapses
          onNavigate={(view: string) => {
            onNavigate(view);
            onCloseMobileDrawer(); // Close drawer after navigation
          }}
          onOpenSettings={() => {
            onOpenSettings();
            onCloseMobileDrawer(); // Close drawer after opening settings
          }}
        />
      </SwipeableDrawer>
    );
  }

  // ========================================
  // DESKTOP: Fixed Sidebar
  // ========================================
  return (
    <Sidebar
      collapsed={collapsed}
      onToggleCollapse={onToggleCollapse}
      onNavigate={onNavigate}
      onOpenSettings={onOpenSettings}
    />
  );
};

export default AppSidebar;
