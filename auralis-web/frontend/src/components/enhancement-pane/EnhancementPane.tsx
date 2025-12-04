/**
 * EnhancementPane Component
 *
 * Main container for the auto-mastering enhancement pane.
 * Displays real-time processing parameters and audio characteristics.
 * 100% design token compliant - zero hardcoded values.
 *
 * Refactored from AutoMasteringPane (585 lines) into 10 focused components.
 */

import React from 'react';
import Collapsed from './views/Collapsed';
import Expanded from './views/Expanded';
import { useEnhancementParameters } from './hooks/useEnhancementParameters';
import { useEnhancement } from '../../contexts/EnhancementContext';

interface EnhancementPaneProps {
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onMasteringToggle?: (enabled: boolean) => void;
}

const EnhancementPane: React.FC<EnhancementPaneProps> = React.memo(({
  collapsed = false,
  onToggleCollapse,
  onMasteringToggle,
}) => {
  const { settings } = useEnhancement();
  const { params, isAnalyzing } = useEnhancementParameters({ enabled: settings.enabled });

  // Collapsed view
  if (collapsed) {
    return <Collapsed onToggleCollapse={onToggleCollapse} />;
  }

  // Expanded view
  return (
    <Expanded
      params={params}
      isAnalyzing={isAnalyzing}
      onToggleCollapse={onToggleCollapse}
      onMasteringToggle={onMasteringToggle}
    />
  );
});

EnhancementPane.displayName = 'EnhancementPane';

export default EnhancementPane;
