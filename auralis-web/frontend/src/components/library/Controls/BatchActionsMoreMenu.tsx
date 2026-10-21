/**
 * BatchActionsMoreMenu - Dropdown menu for additional actions
 *
 * Displayed when "More" button is clicked in batch actions toolbar.
 */

import { Menu, MenuItem } from '@mui/material';
import Edit from '@mui/icons-material/Edit';
import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';

interface BatchActionsMoreMenuProps {
  anchorEl: HTMLElement | null;
  onClose: () => void;
  onEditMetadata: () => void;
}

export const BatchActionsMoreMenu = ({
  anchorEl,
  onClose,
  onEditMetadata,
}: BatchActionsMoreMenuProps) => {
  const handleEditClick = () => {
    onEditMetadata();
    onClose();
  };

  return (
    <Menu
      anchorEl={anchorEl}
      open={Boolean(anchorEl)}
      onClose={onClose}
      anchorOrigin={{
        vertical: 'bottom',
        horizontal: 'right',
      }}
      transformOrigin={{
        vertical: 'top',
        horizontal: 'right',
      }}
      slotProps={{
        paper: {
          sx: {
            // #5641: theme-aware menu surface — the fixed dark gradient left
            // dark ink unreadable on it in light mode.
            background: themeVars.menuSurface,
            border: `1px solid ${tokens.colors.opacityScale.accent.standard}`,
            borderRadius: '12px',
            mt: 1,
          },
        },
      }}
    >
      <MenuItem onClick={handleEditClick} sx={{ color: themeVars.textStrong, gap: 1 }}>
        <Edit fontSize="small" />
        Edit Metadata
      </MenuItem>
    </Menu>
  );
};
