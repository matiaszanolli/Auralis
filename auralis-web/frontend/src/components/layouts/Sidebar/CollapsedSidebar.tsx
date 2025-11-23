import React from 'react';
import { Box, IconButton } from '@mui/material';
import { ChevronRight } from '@mui/icons-material';
import { tokens } from '@/design-system/tokens';
import { CollapsedSidebarContainer } from './SidebarStyles';

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
