/**
 * SearchInputAdornments - Input decorations for search bar
 *
 * Provides start and end adornment components for search input.
 */

import React from 'react';
import { InputAdornment, Box } from '@mui/material';
import { Search, Close } from '@mui/icons-material';
import { ClearButton, ResultCount } from './SearchBar.styles';
import { tokens, CircularProgress } from '@/design-system';

interface SearchInputAdornmentsEndProps {
  value: string;
  resultCount?: number;
  showResultCount?: boolean;
  isSearching?: boolean;
  onClear: () => void;
}

/**
 * Start adornment - search icon
 */
export const SearchInputAdornmentsStart: React.FC = () => (
  <InputAdornment position="start">
    <Search sx={{ fontSize: 20 }} />
  </InputAdornment>
);

/**
 * End adornment - search indicator, result count, and clear button
 */
export const SearchInputAdornmentsEnd: React.FC<SearchInputAdornmentsEndProps> = ({
  value,
  resultCount,
  showResultCount = false,
  isSearching = false,
  onClear,
}) => (
  <InputAdornment position="end">
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      {/* Searching indicator */}
      {isSearching && <CircularProgress size={16} sx={{ color: tokens.colors.text.secondary }} />}

      {/* Result count */}
      {showResultCount && !isSearching && value && resultCount !== undefined && (
        <ResultCount>
          {resultCount} {resultCount === 1 ? 'result' : 'results'}
        </ResultCount>
      )}

      {/* Clear button */}
      {value && (
        <ClearButton size="small" onClick={onClear} aria-label="Clear search">
          <Close sx={{ fontSize: 18 }} />
        </ClearButton>
      )}
    </Box>
  </InputAdornment>
);

/**
 * Convenience export for both adornments
 */
export const SearchInputAdornments = {
  Start: SearchInputAdornmentsStart,
  End: SearchInputAdornmentsEnd,
};
