/**
 * BatchActionsMoreMenu - Dropdown menu for additional actions
 *
 * Displayed when "More" button is clicked in batch actions toolbar.
 */

import React from 'react';
import { Menu, MenuItem } from '@mui/material';
import { Edit } from '@mui/icons-material';
import { tokens } from '@/design-system';

interface BatchActionsMoreMenuProps {
  anchorEl: HTMLElement | null;
  onClose: () => void;
  onEditMetadata: () => void;
}

export const BatchActionsMoreMenu: React.FC<BatchActionsMoreMenuProps> = ({
  anchorEl,
  onClose,
  onEditMetadata,
}) => {
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
      PaperProps={{
        sx: {
          background: tokens.gradients.darkSubtle,
          border: `1px solid ${tokens.colors.opacityScale.accent.standard}`,
          borderRadius: '12px',
          mt: 1,
        },
      }}
    >
      <MenuItem onClick={handleEditClick} sx={{ color: tokens.colors.text.primaryFull, gap: 1 }}>
        <Edit fontSize="small" />
        Edit Metadata
      </MenuItem>
    </Menu>
  );
};
