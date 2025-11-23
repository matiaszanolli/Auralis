import React from 'react';
import { IconButton, Typography } from '@mui/material';
import { Close as CloseIcon } from '@mui/icons-material';
import { StyledDialogTitle } from '../library/Styles/Dialog.styles';

interface SettingsDialogHeaderProps {
  onClose: () => void;
}

/**
 * SettingsDialogHeader - Dialog header with title and close button
 *
 * Displays settings title and close button.
 */
export const SettingsDialogHeader: React.FC<SettingsDialogHeaderProps> = ({ onClose }) => {
  return (
    <StyledDialogTitle>
      <Typography variant="h6" component="span">
        Settings
      </Typography>
      <IconButton onClick={onClose} sx={{ color: 'white' }}>
        <CloseIcon />
      </IconButton>
    </StyledDialogTitle>
  );
};

export default SettingsDialogHeader;
