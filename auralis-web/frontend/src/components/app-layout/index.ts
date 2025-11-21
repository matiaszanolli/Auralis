/**
 * App Layout Components Module
 *
 * This module contains layout-related components used by the main application.
 * Components here handle the overall structure and organization of the UI.
 *
 * Exports:
 * - AppContainer: Top-level layout wrapper with drag-drop support
 * - AppSidebar: Sidebar wrapper (desktop + mobile drawer)
 * - AppTopBar: Header with search and title
 * - AppMainContent: Main content area with library view
 * - AppEnhancementPane: Right panel with enhancement controls
 */

export { AppContainer, type AppContainerProps } from './AppContainer';
export { AppSidebar, type AppSidebarProps } from './AppSidebar';
export { AppTopBar, type AppTopBarProps } from './AppTopBar';
export { AppMainContent, type AppMainContentProps } from './AppMainContent';
export { AppEnhancementPane, type AppEnhancementPaneProps } from './AppEnhancementPane';
