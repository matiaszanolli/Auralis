import { useState, useEffect } from 'react';
import { useMediaQuery, useTheme } from '@mui/material';

/**
 * Hook to manage responsive layout state for the main app.
 * Handles sidebar collapse, mobile drawer visibility, and enhancement pane visibility
 * based on screen size breakpoints.
 *
 * Responsive Behavior:
 * - Mobile (<900px): Sidebar auto-collapses, shows mobile drawer instead
 * - Tablet (<1200px): Enhancement pane auto-collapses
 * - Desktop (>=1200px): All panels visible
 */
export interface LayoutState {
  isMobile: boolean;
  isTablet: boolean;
  sidebarCollapsed: boolean;
  mobileDrawerOpen: boolean;
  presetPaneCollapsed: boolean;
}

export interface LayoutActions {
  setSidebarCollapsed: (collapsed: boolean) => void;
  setMobileDrawerOpen: (open: boolean) => void;
  setPresetPaneCollapsed: (collapsed: boolean) => void;
  toggleSidebarCollapse: () => void;
  toggleMobileDrawer: () => void;
  togglePresetPaneCollapse: () => void;
}

/**
 * Manages responsive layout state and automatically collapses UI elements
 * based on screen size.
 *
 * @returns Layout state and action handlers
 *
 * @example
 * const layout = useAppLayout();
 *
 * // Check if mobile
 * if (layout.isMobile) {
 *   // Show mobile drawer instead of sidebar
 * }
 *
 * // Toggle sidebar on desktop
 * layout.toggleSidebarCollapse();
 */
export const useAppLayout = (): LayoutState & LayoutActions => {
  const theme = useTheme();
  // Mobile: < 900px (theme.breakpoints.down('md'))
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  // Tablet: < 1200px (theme.breakpoints.down('lg'))
  const isTablet = useMediaQuery(theme.breakpoints.down('lg'));

  // Local state for UI collapse/expand
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);
  const [presetPaneCollapsed, setPresetPaneCollapsed] = useState(false);

  // Auto-collapse sidebar on mobile and hide preset pane on tablet
  useEffect(() => {
    if (isMobile) {
      // Mobile: Auto-collapse sidebar and close mobile drawer by default
      setSidebarCollapsed(true);
      setMobileDrawerOpen(false);
    } else {
      // Desktop: Show sidebar
      setSidebarCollapsed(false);
    }
  }, [isMobile]);

  useEffect(() => {
    if (isTablet) {
      // Tablet: Auto-collapse enhancement pane
      setPresetPaneCollapsed(true);
    } else {
      // Desktop: Show enhancement pane
      setPresetPaneCollapsed(false);
    }
  }, [isTablet]);

  const toggleSidebarCollapse = () => {
    setSidebarCollapsed(!sidebarCollapsed);
  };

  const toggleMobileDrawer = () => {
    setMobileDrawerOpen(!mobileDrawerOpen);
  };

  const togglePresetPaneCollapse = () => {
    setPresetPaneCollapsed(!presetPaneCollapsed);
  };

  return {
    // State
    isMobile,
    isTablet,
    sidebarCollapsed,
    mobileDrawerOpen,
    presetPaneCollapsed,
    // Actions
    setSidebarCollapsed,
    setMobileDrawerOpen,
    setPresetPaneCollapsed,
    toggleSidebarCollapse,
    toggleMobileDrawer,
    togglePresetPaneCollapse,
  };
};
