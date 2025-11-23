/**
 * EnhancementPaneV2 Component
 *
 * Main container for the auto-mastering enhancement pane.
 * Displays real-time processing parameters and audio characteristics.
 * 100% design token compliant - zero hardcoded values.
 *
 * Refactored from AutoMasteringPane (585 lines) into 10 focused components.
 */

import React, { useState } from 'react';
import EnhancementPaneCollapsed from './EnhancementPaneCollapsed';
import EnhancementPaneExpanded from './EnhancementPaneExpanded';
import { useEnhancementParameters } from './useEnhancementParameters';
import { useEnhancement } from '../../contexts/EnhancementContext';

interface EnhancementPaneV2Props {
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onMasteringToggle?: (enabled: boolean) => void;
}

const EnhancementPaneV2: React.FC<EnhancementPaneV2Props> = React.memo(({
  collapsed = false,
  onToggleCollapse,
  onMasteringToggle,
}) => {
  const { settings } = useEnhancement();
  const { params, isAnalyzing } = useEnhancementParameters({ enabled: settings.enabled });

  // Collapsed view
  if (collapsed) {
    return <EnhancementPaneCollapsed onToggleCollapse={onToggleCollapse} />;
  }

  // Expanded view
  return (
    <EnhancementPaneExpanded
      params={params}
      isAnalyzing={isAnalyzing}
      onToggleCollapse={onToggleCollapse}
      onMasteringToggle={onMasteringToggle}
    />
  );
});

EnhancementPaneV2.displayName = 'EnhancementPaneV2';

export default EnhancementPaneV2;
