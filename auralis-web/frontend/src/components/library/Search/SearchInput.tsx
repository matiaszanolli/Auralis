import React from 'react';
import {
  InputAdornment,
  CircularProgress
} from '@mui/material';
import {
  Search as SearchIcon,
  Close as CloseIcon
} from '@mui/icons-material';
import {
  SearchContainer,
  SearchField
} from '../Styles/SearchStyles.styles';
import { tokens } from '@/design-system/tokens';

interface SearchInputProps {
  query: string;
  loading: boolean;
  onQueryChange: (query: string) => void;
  onClear: () => void;
}

/**
 * SearchInput - Search input field with loading and clear states
 *
 * Displays:
 * - Text input with placeholder
 * - Search icon or loading spinner
 * - Clear button when query is not empty
 *
 * Props management: Query state and change handlers passed from parent
 */
export const SearchInput: React.FC<SearchInputProps> = ({
  query,
  loading,
  onQueryChange,
  onClear
}) => {
  return (
    <SearchContainer>
      <SearchField
        fullWidth
        placeholder="Search tracks, albums, artists..."
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        InputProps={{
          startAdornment: (
            <InputAdornment position="start">
              {loading ? (
                <CircularProgress size={20} sx={{ color: tokens.colors.accent.purple }} />
              ) : (
                <SearchIcon sx={{ color: 'text.secondary' }} />
              )}
            </InputAdornment>
          ),
          endAdornment: query && (
            <InputAdornment position="end">
              <CloseIcon
                sx={{
                  cursor: 'pointer',
                  color: 'text.secondary',
                  '&:hover': { color: 'text.primary' }
                }}
                onClick={onClear}
              />
            </InputAdornment>
          )
        }}
      />
    </SearchContainer>
  );
};

export default SearchInput;
