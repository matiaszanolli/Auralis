/**
 * SearchKeyboardHint - Keyboard shortcut help text
 *
 * Shows hint for keyboard shortcuts (/, ⌘K) when search is empty
 */

import React from 'react';
import { Typography, Box } from '@mui/material';
import { tokens } from '@/design-system';

interface SearchKeyboardHintProps {
  show: boolean;
}

export const SearchKeyboardHint: React.FC<SearchKeyboardHintProps> = ({ show }) => {
  if (!show) return null;

  return (
    <Typography
      variant="caption"
      sx={{
        display: 'block',
        mt: 0.5,
        ml: 2,
        color: tokens.colors.text.disabled,
        fontSize: '11px',
      }}
    >
      Press{' '}
      <Box
        component="span"
        sx={{
          fontWeight: 'bold',
          color: tokens.colors.text.secondary,
        }}
      >
        /
      </Box>{' '}
      or{' '}
      <Box
        component="span"
        sx={{
          fontWeight: 'bold',
          color: tokens.colors.text.secondary,
        }}
      >
        ⌘K
      </Box>{' '}
      to focus
    </Typography>
  );
};

export default SearchKeyboardHint;
