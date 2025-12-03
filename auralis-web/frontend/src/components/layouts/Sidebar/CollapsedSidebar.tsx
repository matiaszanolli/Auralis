import React from 'react';

import { ChevronRight } from '@mui/icons-material';
import { tokens } from '@/design-system';
import { CollapsedSidebarContainer } from './SidebarStyles';
import { IconButton } from '@/design-system';
import { Box } from '@mui/material';

interface CollapsedSidebarProps {
  onToggleCollapse?: () => void;
}

/**
 * CollapsedSidebar - Minimal sidebar when collapsed
 *
 * Shows only toggle button to expand sidebar
 */
export const CollapsedSidebar: React.FC<CollapsedSidebarProps> = ({ onToggleCollapse }) => {
  return (
    <CollapsedSidebarContainer>
      <Box sx={{ p: tokens.spacing.md, display: 'flex', justifyContent: 'center' }}>
        <IconButton onClick={onToggleCollapse} sx={{ color: tokens.colors.text.secondary }}>
          <ChevronRight />
        </IconButton>
      </Box>
    </CollapsedSidebarContainer>
  );
};

export default CollapsedSidebar;
