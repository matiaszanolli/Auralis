import React from 'react';
import { IconButton, Typography } from '@mui/material';
import { Close, Keyboard } from '@mui/icons-material';
import { StyledDialogTitle } from '../library/Styles/Dialog.styles';
import { tokens } from '@/design-system';

interface KeyboardShortcutsHeaderProps {
  onClose: () => void;
}

/**
 * KeyboardShortcutsHeader - Dialog header with close button
 *
 * Displays:
 * - Keyboard icon with title
 * - Close button to dismiss dialog
 */
export const KeyboardShortcutsHeader: React.FC<KeyboardShortcutsHeaderProps> = ({ onClose }) => {
  return (
    <StyledDialogTitle>
      <Keyboard />
      <Typography variant="h6" component="div" sx={{ flex: 1 }}>
        Keyboard Shortcuts
      </Typography>
      <IconButton
        onClick={onClose}
        sx={{
          color: tokens.colors.text.primary,
          '&:hover': {
            background: 'rgba(102, 126, 234, 0.05)',
          },
        }}
      >
        <Close />
      </IconButton>
    </StyledDialogTitle>
  );
};

export default KeyboardShortcutsHeader;
