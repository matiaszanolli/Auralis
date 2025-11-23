import React, { useState, useEffect } from 'react';
import { Box } from '@mui/material';
import { SearchTextField } from '../library/Styles/FormFields.styles';
import { SearchInputAdornments } from './SearchInputAdornments';
import { SearchKeyboardHint } from './SearchKeyboardHint';

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
          startAdornment: <SearchInputAdornments.Start />,
          endAdornment: (
            <SearchInputAdornments.End
              value={internalValue}
              resultCount={resultCount}
              showResultCount={showResultCount}
              isSearching={isSearching}
              onClear={handleClear}
            />
          ),
        }}
      />

      <SearchKeyboardHint show={!internalValue && !autoFocus} />
    </Box>
  );
};

export default SearchBar;
