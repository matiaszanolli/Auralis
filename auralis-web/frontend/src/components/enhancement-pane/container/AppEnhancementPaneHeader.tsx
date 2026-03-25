/**
 * AppEnhancementPaneHeader Component
 *
 * Header with title and collapse/expand toggle
 */

import React from 'react';

import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { PaneHeader, PaneTitle } from './AppEnhancementPaneStyles';
import { IconButton, Tooltip, tokens } from '@/design-system';

interface AppEnhancementPaneHeaderProps {
  isCollapsed: boolean;
  useV2: boolean;
  onToggleCollapse: () => void;
}

export const AppEnhancementPaneHeader = ({
  isCollapsed,
  useV2,
  onToggleCollapse,
}: AppEnhancementPaneHeaderProps) => {
  return (
    <PaneHeader>
      {!isCollapsed && (
        <PaneTitle>
          {useV2 ? 'Enhancement V2' : 'Enhancement'}
        </PaneTitle>
      )}

      <Tooltip title={isCollapsed ? 'Expand' : 'Collapse'}>
        <IconButton
          onClick={onToggleCollapse}
          aria-label={isCollapsed ? 'Expand enhancement pane' : 'Collapse enhancement pane'}
          aria-expanded={!isCollapsed}
          size="small"
          sx={{
            color: tokens.colors.text.secondary,
            padding: '4px',
            '&:hover': {
              color: tokens.colors.text.secondary,
              background: tokens.colors.opacityScale.accent.veryLight,
            },
          }}
        >
          {isCollapsed ? (
            <ExpandMoreIcon fontSize="small" />
          ) : (
            <ExpandLessIcon fontSize="small" />
          )}
        </IconButton>
      </Tooltip>
    </PaneHeader>
  );
};
