import React from 'react';

import { Close as CloseIcon } from '@mui/icons-material';
import { StyledDialogTitle } from '@/components/library/Styles/Dialog.styles';
import { IconButton, tokens } from '@/design-system';
import { Typography } from '@mui/material';

interface SettingsDialogHeaderProps {
  onClose: () => void;
}

/**
 * SettingsDialogHeader - Dialog header with title and close button
 *
 * Displays settings title and close button.
 */
export const SettingsDialogHeader = ({ onClose }: SettingsDialogHeaderProps) => {
  return (
    <StyledDialogTitle>
      <Typography variant="h6" component="span">
        Settings
      </Typography>
      <IconButton onClick={onClose} sx={{ color: tokens.colors.text.primaryFull }}>
        <CloseIcon />
      </IconButton>
    </StyledDialogTitle>
  );
};

export default SettingsDialogHeader;
