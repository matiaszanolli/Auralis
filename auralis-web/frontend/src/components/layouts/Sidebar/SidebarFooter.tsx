/**
 * SidebarFooter - Sidebar footer with settings and theme toggle
 */

import React from 'react';
import { Box, ListItemIcon, ListItemText } from '@mui/material';
import { Settings } from '@mui/icons-material';
import { tokens } from '@/design-system/tokens';
import ThemeToggle from '../../shared/ui/ThemeToggle';
import { StyledListItemButton } from './SidebarStyles';

interface SidebarFooterProps {
  onOpenSettings?: () => void;
}

export const SidebarFooter: React.FC<SidebarFooterProps> = ({ onOpenSettings }) => {
  return (
    <Box sx={{ mt: 'auto', p: tokens.spacing.md, borderTop: `1px solid ${tokens.colors.border.light}` }}>
      {/* Settings Button */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: tokens.spacing.sm, mb: tokens.spacing.sm }}>
        <Box sx={{ flex: 1 }}>
          <StyledListItemButton onClick={onOpenSettings} isactive="false">
            <ListItemIcon
              sx={{
                color: tokens.colors.text.secondary,
                minWidth: `calc(${tokens.spacing.lg} + ${tokens.spacing.sm})`, // 36px
                transition: tokens.transitions.color,
              }}
            >
              <Settings />
            </ListItemIcon>
            <ListItemText
              primary="Settings"
              primaryTypographyProps={{
                fontSize: tokens.typography.fontSize.base,
                fontWeight: tokens.typography.fontWeight.normal,
                color: tokens.colors.text.secondary,
              }}
            />
          </StyledListItemButton>
        </Box>
      </Box>

      {/* Theme Toggle */}
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: tokens.spacing.md }}>
        <ThemeToggle size="medium" />
      </Box>
    </Box>
  );
};

export default SidebarFooter;
