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

export const AppEnhancementPaneHeader: React.FC<AppEnhancementPaneHeaderProps> = ({
  isCollapsed,
  useV2,
  onToggleCollapse,
}) => {
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
          size="small"
          sx={{
            color: 'rgba(255, 255, 255, 0.5)',
            padding: '4px',
            '&:hover': {
              color: 'var(--silver)',
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
