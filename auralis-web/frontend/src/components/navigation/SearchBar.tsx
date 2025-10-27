import React, { useState, useEffect } from 'react';
import { TextField, InputAdornment, styled, Typography, Box, CircularProgress } from '@mui/material';
import { Search, Close } from '@mui/icons-material';
import { colors } from '../../theme/auralisTheme';
import { IconButton } from '@mui/material';

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

const StyledSearchField = styled(TextField)(({ theme }) => ({
  '& .MuiOutlinedInput-root': {
    height: '48px',
    borderRadius: '24px',
    background: 'rgba(26, 31, 58, 0.5)',
    backdropFilter: 'blur(8px)',
    border: '1px solid transparent',
    transition: 'all 0.3s ease',
    paddingRight: '8px',

    '& fieldset': {
      border: 'none',
    },

    '&:hover': {
      background: 'rgba(26, 31, 58, 0.7)',
      border: '1px solid rgba(102, 126, 234, 0.2)',
    },

    '&.Mui-focused': {
      background: 'rgba(26, 31, 58, 0.8)',
      border: '1px solid rgba(102, 126, 234, 0.5)',
      boxShadow: '0 0 0 3px rgba(102, 126, 234, 0.1)',
    },
  },

  '& .MuiOutlinedInput-input': {
    fontSize: '16px',
    color: colors.text.primary,
    padding: '12px 16px',

    '&::placeholder': {
      color: colors.text.secondary,
      opacity: 1,
    },
  },

  '& .MuiInputAdornment-root': {
    marginRight: '8px',
    color: colors.text.secondary,
  },
}));

const ClearButton = styled(IconButton)({
  padding: '8px',
  color: colors.text.secondary,
  transition: 'all 0.2s ease',

  '&:hover': {
    color: colors.text.primary,
    background: 'rgba(102, 126, 234, 0.1)',
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
      <StyledSearchField
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
                    sx={{ color: colors.text.secondary }}
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
            color: colors.text.disabled,
            fontSize: '11px',
          }}
        >
          Press <Box component="span" sx={{ fontWeight: 'bold', color: colors.text.secondary }}>/</Box> or{' '}
          <Box component="span" sx={{ fontWeight: 'bold', color: colors.text.secondary }}>⌘K</Box> to focus
        </Typography>
      )}
    </Box>
  );
};

export default SearchBar;
