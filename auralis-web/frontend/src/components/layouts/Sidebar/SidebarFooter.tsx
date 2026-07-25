/**
 * SidebarFooter - Sidebar footer with settings and theme toggle
 */

import { Box, ListItemIcon, ListItemText } from '@mui/material';
import Settings from '@mui/icons-material/Settings';
import { tokens } from '@/design-system';
import ThemeToggle from '@/components/shared/ui/ThemeToggle';
import { StyledListItemButton } from './SidebarStyles';
import { themeVars } from '@/theme/semanticTheme';

interface SidebarFooterProps {
  onOpenSettings?: () => void;
}

export const SidebarFooter = ({ onOpenSettings }: SidebarFooterProps) => {
  return (
    <Box sx={{ mt: 'auto', p: tokens.spacing.md, borderTop: `1px solid ${themeVars.borderSubtle}` }}>
      {/* Settings Button */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: tokens.spacing.sm, mb: tokens.spacing.sm }}>
        <Box sx={{ flex: 1 }}>
          <StyledListItemButton onClick={onOpenSettings} isactive="false">
            <ListItemIcon
              sx={{
                color: themeVars.textSecondary,
                minWidth: `calc(${tokens.spacing.lg} + ${tokens.spacing.sm})`, // 36px
                transition: tokens.transitions.color,
              }}
            >
              <Settings />
            </ListItemIcon>
            <ListItemText
              primary="Settings"
              slotProps={{
                primary: {
                  sx: {
                    fontSize: tokens.typography.fontSize.base,
                    fontWeight: tokens.typography.fontWeight.normal,
                    color: themeVars.textSecondary,
                  },
                },
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
