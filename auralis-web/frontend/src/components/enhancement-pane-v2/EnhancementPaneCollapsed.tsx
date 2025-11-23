import React from 'react';
import { IconButton, Tooltip } from '@mui/material';
import { ChevronLeft, AutoAwesome } from '@mui/icons-material';
import { tokens } from '../../design-system/tokens';
import {
  CollapsedPaneContainer,
  CollapsedIconContainer,
} from './EnhancementPaneV2.styles';

interface EnhancementPaneCollapsedProps {
  onToggleCollapse?: () => void;
}

/**
 * EnhancementPaneCollapsed - Collapsed view of enhancement pane
 *
 * Shows only icon and collapse button when collapsed.
 */
export const EnhancementPaneCollapsed: React.FC<EnhancementPaneCollapsedProps> = ({
  onToggleCollapse,
}) => {
  return (
    <CollapsedPaneContainer>
      <IconButton onClick={onToggleCollapse} sx={{ color: tokens.colors.text.primary }}>
        <ChevronLeft />
      </IconButton>
      <CollapsedIconContainer>
        <Tooltip title="Auto-Mastering" placement="left">
          <AutoAwesome sx={{ color: tokens.colors.accent.primary }} />
        </Tooltip>
      </CollapsedIconContainer>
    </CollapsedPaneContainer>
  );
};

export default EnhancementPaneCollapsed;
