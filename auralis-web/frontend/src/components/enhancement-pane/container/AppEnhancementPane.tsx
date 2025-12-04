/**
 * AppEnhancementPane Component (Refactored)
 *
 * Right panel for audio enhancement controls.
 * Refactored from 234 lines using extracted components and helpers.
 *
 * Extracted modules:
 * - AppEnhancementPaneStyles - Styled components
 * - useAppEnhancementPaneState - Collapse state hook
 * - AppEnhancementPaneHeader - Header with toggle
 * - AppEnhancementPaneFooter - V2 toggle button
 */

import React from 'react';
import { PaneContainer, ContentArea } from './AppEnhancementPaneStyles';
import { AppEnhancementPaneHeader } from './AppEnhancementPaneHeader';
import { AppEnhancementPaneFooter } from './AppEnhancementPaneFooter';
import { useAppEnhancementPaneState } from './useAppEnhancementPaneState';

/**
 * Props for the AppEnhancementPane component.
 */
export interface AppEnhancementPaneProps {
  /**
   * Callback when enhancement parameters are changed.
   */
  onEnhancementChange?: (params: Record<string, any>) => void;

  /**
   * Callback when V2 toggle is activated.
   */
  onToggleV2?: () => void;

  /**
   * Whether to show the V2 enhancement pane.
   */
  useV2?: boolean;

  /**
   * Whether enhancement pane is initially collapsed.
   */
  initiallyCollapsed?: boolean;

  /**
   * Child components to render inside the pane.
   */
  children: React.ReactNode;
}

/**
 * AppEnhancementPane - Main orchestrator component
 *
 * Provides the right panel for audio enhancement controls with:
 * - Collapsible layout
 * - Header with version title
 * - Content area for enhancement controls
 * - Footer with V2 toggle
 */
export const AppEnhancementPane: React.FC<AppEnhancementPaneProps> = ({
  onEnhancementChange,
  onToggleV2,
  useV2 = false,
  initiallyCollapsed = false,
  children,
}) => {
  const { isCollapsed, handleCollapsedToggle } = useAppEnhancementPaneState(initiallyCollapsed);

  return (
    <PaneContainer isCollapsed={isCollapsed}>
      {/* Header with collapse toggle */}
      <AppEnhancementPaneHeader
        isCollapsed={isCollapsed}
        useV2={useV2}
        onToggleCollapse={handleCollapsedToggle}
      />

      {/* Content area */}
      {!isCollapsed && (
        <ContentArea>
          {children}
        </ContentArea>
      )}

      {/* V2 toggle button */}
      {!isCollapsed && (
        <AppEnhancementPaneFooter
          useV2={useV2}
          onToggleV2={onToggleV2}
        />
      )}
    </PaneContainer>
  );
};

export default AppEnhancementPane;
