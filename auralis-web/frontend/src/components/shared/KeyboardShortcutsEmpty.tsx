import React from 'react';
import { Typography } from '@mui/material';
import { Keyboard } from '@mui/icons-material';
import { EmptyStateBox } from './KeyboardShortcutsHelp.styles';

/**
 * KeyboardShortcutsEmpty - Empty state when no shortcuts are configured
 *
 * Displays:
 * - Large keyboard icon
 * - Helpful message explaining why no shortcuts are shown
 */
export const KeyboardShortcutsEmpty: React.FC = () => {
  return (
    <EmptyStateBox>
      <Keyboard sx={{ fontSize: 64, mb: 2, opacity: 0.3 }} />
      <Typography variant="h6" gutterBottom>
        No keyboard shortcuts configured
      </Typography>
      <Typography variant="body2">
        Enable keyboard shortcuts in settings to see available shortcuts here.
      </Typography>
    </EmptyStateBox>
  );
};

export default KeyboardShortcutsEmpty;
