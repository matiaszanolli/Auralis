/**
 * SidebarHeader - Sidebar header with logo and collapse button
 */

import React from 'react';
import { Box, Divider, IconButton } from '@mui/material';
import { ChevronLeft } from '@mui/icons-material';
import { tokens } from '@/design-system/tokens';
import { AuroraLogo } from '../../navigation/AuroraLogo';

interface SidebarHeaderProps {
  onToggleCollapse?: () => void;
}

export const SidebarHeader: React.FC<SidebarHeaderProps> = ({ onToggleCollapse }) => {
  return (
    <>
      <Box
        sx={{
          p: tokens.spacing.md,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <AuroraLogo size="medium" showText animated />
        <IconButton
          onClick={onToggleCollapse}
          size="small"
          sx={{
            color: tokens.colors.text.secondary,
            transition: tokens.transitions.all,
            '&:hover': {
              color: tokens.colors.text.primary,
              transform: 'scale(1.1)',
            },
          }}
        >
          <ChevronLeft />
        </IconButton>
      </Box>

      <Divider sx={{ borderColor: tokens.colors.border.light }} />
    </>
  );
};

export default SidebarHeader;
