
import ChevronRight from '@mui/icons-material/ChevronRight';
import { tokens } from '@/design-system';
import { CollapsedSidebarContainer } from './SidebarStyles';
import { IconButton } from '@/design-system';
import { Box } from '@mui/material';
import { themeVars } from '@/theme/semanticTheme';

interface CollapsedSidebarProps {
  onToggleCollapse?: () => void;
}

/**
 * CollapsedSidebar - Minimal sidebar when collapsed
 *
 * Shows only toggle button to expand sidebar
 */
export const CollapsedSidebar = ({ onToggleCollapse }: CollapsedSidebarProps) => {
  return (
    <CollapsedSidebarContainer>
      <Box sx={{ p: tokens.spacing.md, display: 'flex', justifyContent: 'center' }}>
        <IconButton onClick={onToggleCollapse} aria-label="Expand sidebar" aria-expanded={false} sx={{ color: themeVars.textSecondary }}>
          <ChevronRight />
        </IconButton>
      </Box>
    </CollapsedSidebarContainer>
  );
};

export default CollapsedSidebar;
