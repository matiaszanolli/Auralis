/**
 * SidebarHeader - Sidebar header with logo and collapse button
 */

import ChevronLeft from '@mui/icons-material/ChevronLeft';
import { tokens } from '@/design-system';
import { AuroraLogo } from '@/components/navigation/AuroraLogo';
import { IconButton } from '@/design-system';
import { Box, Divider } from '@mui/material';
import { themeVars } from '@/theme/semanticTheme';

interface SidebarHeaderProps {
  onToggleCollapse?: () => void;
}

export const SidebarHeader = ({ onToggleCollapse }: SidebarHeaderProps) => {
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
          aria-label="Collapse sidebar"
          aria-expanded={true}
          size="small"
          sx={{
            color: themeVars.textSecondary,
            transition: tokens.transitions.all,
            '&:hover': {
              color: themeVars.textPrimary,
            },
          }}
        >
          <ChevronLeft />
        </IconButton>
      </Box>

      <Divider sx={{ borderColor: themeVars.borderSubtle }} />
    </>
  );
};

export default SidebarHeader;
