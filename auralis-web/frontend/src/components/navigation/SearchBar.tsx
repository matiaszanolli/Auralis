import React, { useState, useEffect } from 'react';
import { TextField, InputAdornment, styled } from '@mui/material';
import { Search, Close } from '@mui/icons-material';
import { colors } from '../../theme/auralisTheme';
import { IconButton } from '@mui/material';

interface SearchBarProps {
  value?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  debounceMs?: number;
  autoFocus?: boolean;
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

export const SearchBar: React.FC<SearchBarProps> = ({
  value: controlledValue,
  onChange,
  placeholder = 'Search',
  debounceMs = 300,
  autoFocus = false,
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
        endAdornment: internalValue && (
          <InputAdornment position="end">
            <ClearButton
              size="small"
              onClick={handleClear}
              aria-label="Clear search"
            >
              <Close sx={{ fontSize: 18 }} />
            </ClearButton>
          </InputAdornment>
        ),
      }}
    />
  );
};

export default SearchBar;
