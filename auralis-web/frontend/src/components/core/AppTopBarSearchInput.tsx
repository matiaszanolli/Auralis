import React from 'react';

import SearchIcon from '@mui/icons-material/Search';
import CloseIcon from '@mui/icons-material/Close';
import { auroraOpacity } from '../library/Styles/Color.styles';
import { SearchContainer } from './AppTopBar.styles';
import { IconButton } from '@/design-system';
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
export const AppTopBarSearchInput: React.FC<AppTopBarSearchInputProps> = ({
  searchQuery,
  isSearchFocused,
  minWidth,
  onSearchChange,
  onFocus,
  onBlur,
  onClear,
}) => {
  return (
    <SearchContainer focused={isSearchFocused} sx={{ minWidth }}>
      <SearchIcon
        sx={{
          color: auroraOpacity.stronger,
          fontSize: '18px',
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
            color: 'var(--silver)',
            fontSize: '14px',
            '&::placeholder': {
              color: auroraOpacity.standard,
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
            color: auroraOpacity.stronger,
            padding: '4px',
            '&:hover': {
              color: 'var(--silver)',
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
