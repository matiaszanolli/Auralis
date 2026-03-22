import React from 'react';

import SearchIcon from '@mui/icons-material/Search';
import CloseIcon from '@mui/icons-material/Close';
import { SearchContainer } from './AppTopBar.styles';
import { IconButton, tokens } from '@/design-system';
import { TextField } from '@mui/material';

interface AppTopBarSearchInputProps {
  searchQuery: string;
  isSearchFocused: boolean;
  minWidth: number;
  onSearchChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onFocus: () => void;
  onBlur: () => void;
  onClear: () => void;
}

/**
 * AppTopBarSearchInput - Search input field with icon and clear button
 *
 * Displays search icon, input field, and optional clear button.
 */
export const AppTopBarSearchInput = ({
  searchQuery,
  isSearchFocused,
  minWidth,
  onSearchChange,
  onFocus,
  onBlur,
  onClear,
}: AppTopBarSearchInputProps) => {
  return (
    <SearchContainer focused={isSearchFocused} sx={{ minWidth }}>
      <SearchIcon
        sx={{
          color: tokens.colors.opacityScale.accent.veryStrong,
          fontSize: tokens.typography.fontSize.lg,
          opacity: 0.6,
        }}
      />
      <TextField
        placeholder="Search tracks, albums, artists..."
        value={searchQuery}
        onChange={onSearchChange}
        onFocus={onFocus}
        onBlur={onBlur}
        sx={{
          flex: 1,
          '& .MuiOutlinedInput-root': {
            border: 'none',
            padding: 0,
          },
          '& .MuiOutlinedInput-input': {
            padding: 0,
            color: tokens.colors.text.secondary,
            fontSize: tokens.typography.fontSize.base,
            '&::placeholder': {
              color: tokens.colors.opacityScale.accent.standard,
              opacity: 1,
            },
          },
          '& .MuiOutlinedInput-notchedOutline': {
            border: 'none',
          },
        }}
      />
      {searchQuery && (
        <IconButton
          onClick={onClear}
          size="small"
          sx={{
            color: tokens.colors.opacityScale.accent.veryStrong,
            padding: '4px',
            '&:hover': {
              color: tokens.colors.text.secondary,
            },
          }}
        >
          <CloseIcon fontSize="small" />
        </IconButton>
      )}
    </SearchContainer>
  );
};

export default AppTopBarSearchInput;
