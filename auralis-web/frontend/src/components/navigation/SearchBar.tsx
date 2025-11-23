import React, { useState, useEffect } from 'react';
import { InputAdornment, styled, Typography, Box, CircularProgress } from '@mui/material';
import { Search, Close } from '@mui/icons-material';
import { colors } from '../../theme/auralisTheme';
import { IconButton } from '@mui/material';
import { SearchTextField } from '../../components/library/FormFields.styles';
import { auroraOpacity } from '../library/Color.styles';
import { tokens } from '@/design-system/tokens';

interface SearchBarProps {
  value?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  debounceMs?: number;
  autoFocus?: boolean;
  resultCount?: number;
  showResultCount?: boolean;
  isSearching?: boolean;
}

const ClearButton = styled(IconButton)({
  padding: '8px',
  color: colors.text.secondary,
  transition: 'all 0.2s ease',

  '&:hover': {
    color: colors.text.primary,
    background: auroraOpacity.ultraLight,
  },
});

const ResultCount = styled(Typography)({
  fontSize: '12px',
  fontWeight: 500,
  color: colors.text.secondary,
  padding: '0 12px',
  whiteSpace: 'nowrap',
});

export const SearchBar: React.FC<SearchBarProps> = ({
  value: controlledValue,
  onChange,
  placeholder = 'Search tracks, albums, artists...',
  debounceMs = 300,
  autoFocus = false,
  resultCount,
  showResultCount = false,
  isSearching = false,
}) => {
  const [internalValue, setInternalValue] = useState(controlledValue || '');
  const [debouncedValue, setDebouncedValue] = useState(internalValue);

  // Sync with controlled value
  useEffect(() => {
    if (controlledValue !== undefined) {
      setInternalValue(controlledValue);
    }
  }, [controlledValue]);

  // Debounce the search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(internalValue);
    }, debounceMs);

    return () => clearTimeout(timer);
  }, [internalValue, debounceMs]);

  // Call onChange with debounced value
  useEffect(() => {
    if (onChange && debouncedValue !== controlledValue) {
      onChange(debouncedValue);
    }
  }, [debouncedValue, onChange, controlledValue]);

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setInternalValue(event.target.value);
  };

  const handleClear = () => {
    setInternalValue('');
    if (onChange) {
      onChange('');
    }
  };

  return (
    <Box sx={{ width: '100%' }}>
      <SearchTextField
        fullWidth
        variant="outlined"
        placeholder={placeholder}
        value={internalValue}
        onChange={handleChange}
        autoFocus={autoFocus}
        InputProps={{
          startAdornment: (
            <InputAdornment position="start">
              <Search sx={{ fontSize: 20 }} />
            </InputAdornment>
          ),
          endAdornment: (
            <InputAdornment position="end">
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {/* Searching indicator */}
                {isSearching && (
                  <CircularProgress
                    size={16}
                    sx={{ color: tokens.colors.text.secondary }}
                  />
                )}

                {/* Result count */}
                {showResultCount && !isSearching && internalValue && resultCount !== undefined && (
                  <ResultCount>
                    {resultCount} {resultCount === 1 ? 'result' : 'results'}
                  </ResultCount>
                )}

                {/* Clear button */}
                {internalValue && (
                  <ClearButton
                    size="small"
                    onClick={handleClear}
                    aria-label="Clear search"
                  >
                    <Close sx={{ fontSize: 18 }} />
                  </ClearButton>
                )}
              </Box>
            </InputAdornment>
          ),
        }}
      />

      {/* Keyboard shortcut hint */}
      {!internalValue && !autoFocus && (
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
          Press <Box component="span" sx={{ fontWeight: 'bold', color: tokens.colors.text.secondary }}>/</Box> or{' '}
          <Box component="span" sx={{ fontWeight: 'bold', color: tokens.colors.text.secondary }}>⌘K</Box> to focus
        </Typography>
      )}
    </Box>
  );
};

export default SearchBar;
