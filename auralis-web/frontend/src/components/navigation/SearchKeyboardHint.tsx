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
  // Hide keyboard hint to reduce visual noise - search should feel ambient
  return null;
};

export default SearchKeyboardHint;
